# Chapter 3 — Key Concepts & Design Principles

## Pluggable Adapters

### The Problem
Different users need different providers:
- LLM: OpenAI, Vertex AI, Claude, etc.
- TTS: ElevenLabs, Google, AWS Polly, etc.
- Images: Stability, Replicate, DALL-E, etc.

Hard-coding a single provider makes the system inflexible.

### The Solution: Adapter Pattern

Define an **interface** that all implementations must follow:

```python
# adapters/schema.py
from abc import ABC, abstractmethod

class LLMAdapter(ABC):
    """Interface all LLM adapters must implement"""
    
    @abstractmethod
    def generate(self, messages: List[Dict]) -> str:
        """Generate text from messages"""
        pass

class TTSAdapter(ABC):
    """Interface all TTS adapters must implement"""
    
    @abstractmethod
    def synthesize(self, text: str, voice: str) -> bytes:
        """Synthesize speech to WAV audio"""
        pass

class ImageAdapter(ABC):
    """Interface all image adapters must implement"""
    
    @abstractmethod
    def generate_image(self, description: str) -> str:
        """Generate image from description, return PNG file path"""
        pass
```

Then **implement for each provider**:

```python
# adapters/openai_adapter.py
class OpenAIAdapter(LLMAdapter):
    def generate(self, messages: List[Dict]) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        return response.choices[0].message.content

# adapters/google_vertex_adapter.py
class GoogleVertexAdapter(LLMAdapter):
    def generate(self, messages: List[Dict]) -> str:
        response = self.client.generate_content(
            contents=messages
        )
        return response.text
```

### Benefit: Swappability

The rest of the code uses adapters generically:

```python
# script_generator.py
def generate(self, chapter_text: str) -> Dict:
    llm = get_llm_adapter()  # Could be any provider
    messages = [{"role": "user", "content": f"Generate slides:\n{chapter_text}"}]
    response = llm.generate(messages)  # Works with any adapter
    return self._parse_response(response)
```

Switch providers with one environment variable:
```bash
LLM_PROVIDER=openai python -m agent.cli ...
LLM_PROVIDER=vertex python -m agent.cli ...
```

## Factory Functions

### The Problem
Creating adapters requires knowing:
- Which class to instantiate
- What parameters it needs
- Whether dependencies are available

Scattered across the code, this becomes hard to maintain.

### The Solution: Centralized Factory

**Location**: `adapters/factory.py`

```python
def get_llm_adapter(provider: Optional[str] = None) -> LLMAdapter:
    """
    Create LLM adapter based on provider.
    
    - Resolves provider from parameter, environment, or default
    - Handles missing dependencies gracefully
    - Logs creation for debugging
    """
    chosen = provider or os.getenv("LLM_PROVIDER") or "vertex"
    
    logger.debug("Resolving LLM adapter: %s", chosen)
    
    if chosen == "openai":
        try:
            adapter = OpenAIAdapter()
            logger.info("Initialized OpenAI LLM adapter")
            return adapter
        except ImportError as e:
            logger.warning("OpenAI not available, falling back: %s", e)
            return DummyLLMAdapter()
    
    if chosen == "vertex":
        adapter = GoogleVertexAdapter()
        logger.info("Initialized Vertex LLM adapter")
        return adapter
    
    logger.warning("Unknown provider %s, using dummy", chosen)
    return DummyLLMAdapter()
```

### Benefits

1. **Single Source of Truth** - One place for provider logic
2. **Dependency Handling** - Graceful fallback if package not installed
3. **Consistent Logging** - All adapter creation logged
4. **Easy Testing** - Can mock factory for tests
5. **Environment Aware** - Reads from environment/config

## Retry Pattern with Backoff

### The Problem
APIs fail:
- **Transient**: Rate limit (429), timeout, temporary service issue
- **Permanent**: Authentication failure (401), not found (404)

Retrying permanent errors wastes time. Not retrying transient errors loses data.

### The Solution: Smart Retry

**Location**: `llm_client.py`

```python
def call_with_retries(func, max_retries=3, backoff_base=2):
    """
    Call function with exponential backoff retry.
    
    Only retries on transient errors.
    Fails immediately on permanent errors.
    """
    for attempt in range(max_retries):
        try:
            return func()
        
        except (APIError, TimeoutError, RateLimitError) as e:
            # Transient errors - retry
            if attempt == max_retries - 1:
                logger.error("Max retries exceeded: %s", e)
                raise
            
            # Exponential backoff: 2^attempt seconds
            wait_time = backoff_base ** attempt
            logger.warning(
                "Attempt %d/%d failed, retrying in %d seconds: %s",
                attempt + 1, max_retries, wait_time, e
            )
            time.sleep(wait_time)
        
        except AuthenticationError as e:
            # Permanent error - fail immediately
            logger.error("Authentication failed: %s", e)
            raise
        
        except Exception as e:
            # Unknown error - fail immediately
            logger.error("Unexpected error: %s", e)
            raise
```

### Backoff Strategy

```
Attempt 1: Fail immediately
Attempt 2: Retry after 2^1 = 2 seconds
Attempt 3: Retry after 2^2 = 4 seconds
Attempt 4: Retry after 2^3 = 8 seconds
(Fail after 4 attempts)
```

**Why exponential?**
- Gives service time to recover
- Spreads load over time
- Doesn't retry forever

## Thread-Safe State Management

### The Problem
Multiple parallel workers generating assets concurrently. They all need to save progress (checkpoints).

**Without synchronization**:
```
Worker 1: Read checkpoint {slides: [1,2]}
Worker 2: Read checkpoint {slides: [1,2]}
Worker 1: Update to {slides: [1,2,3]}
Worker 2: Update to {slides: [1,2,4]} (lost Worker 1's update!)
Worker 1: Write {slides: [1,2,3]} ← Corrupted!
Worker 2: Write {slides: [1,2,4]}
```

### The Solution: Atomic Operations + Locking

**Location**: `runs_safe.py`

```python
def save_checkpoint_atomic(run_id: str, node: str, data: Dict) -> None:
    """Thread-safe checkpoint save using file locking"""
    
    # 1. Acquire exclusive lock
    lock_file = f"checkpoints/{run_id}.lock"
    lock_handle = _acquire_lock(lock_file, timeout=5.0)
    
    try:
        checkpoint_file = f"checkpoints/{run_id}.json"
        
        # 2. Read current state
        current = {}
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file) as f:
                current = json.load(f)
        
        # 3. Update specific node
        current[node] = data
        current["updated_at"] = datetime.utcnow().isoformat()
        
        # 4. Write to temporary file
        temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(checkpoint_file))
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(current, f)
            
            # 5. Atomic rename to final location
            os.replace(temp_path, checkpoint_file)
            logger.debug("Checkpoint saved for node: %s", node)
        
        except:
            os.unlink(temp_path)
            raise
    
    finally:
        # 6. Release lock
        _release_lock(lock_handle)
```

### Why This Works

1. **Lock**: Only one worker at a time
2. **Temp file**: Write doesn't interfere with reads
3. **Atomic rename**: Either completes fully or not at all
4. **Timeout**: Prevents deadlocks

**Result**: Multiple workers can safely write concurrent checkpoints.

## Rate Limiting

### The Problem
APIs have rate limits. Hitting them:
- Causes 429 (Too Many Requests) errors
- Wastes bandwidth/quota
- Can get IP banned

### The Solution: Token Bucket

**Location**: `parallel.py`

```python
class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, calls_per_second: float):
        self.rate = calls_per_second
        self.last_call = time.time()
    
    def wait_if_needed(self):
        """Block until safe to make next call"""
        elapsed = time.time() - self.last_call
        required_wait = 1.0 / self.rate
        
        if elapsed < required_wait:
            time.sleep(required_wait - elapsed)
        
        self.last_call = time.time()
```

### Usage

```python
# Max 2 API calls per second
limiter = RateLimiter(calls_per_second=2.0)

for item in items:
    limiter.wait_if_needed()
    api_call(item)  # Never exceeds 2/sec
```

## Graceful Degradation

### The Principle
System should work even when not all providers available.

### Implementation

1. **Try real implementation**
2. **Fall back to dummy on ImportError**

```python
def get_image_adapter(provider: Optional[str] = None) -> ImageAdapter:
    chosen = provider or "stability"
    
    if chosen == "stability":
        try:
            return StabilityImageAdapter()
        except ImportError:
            logger.warning("Stability not installed, using dummy")
            return DummyImageAdapter()
    
    return DummyImageAdapter()
```

### Result
- Works offline with dummy providers
- Works with real providers when installed
- Graceful error messages
- Testable without external services

## Validation Pattern

### The Problem
APIs return JSON, but is it valid?

### The Solution: Schema Validation

```python
from pydantic import BaseModel, ValidationError

class SlideSchema(BaseModel):
    slide_number: int
    title: str
    script: str
    image_description: str

def generate_script(chapter_text: str) -> Dict:
    llm = get_llm_adapter()
    response = llm.generate(messages)
    
    try:
        # Parse JSON
        data = json.loads(response)
        
        # Validate schema
        slides = [SlideSchema(**slide) for slide in data["slides"]]
        
        logger.info("Validated %d slides", len(slides))
        return {"slides": [s.model_dump() for s in slides]}
    
    except ValidationError as e:
        logger.error("Validation failed: %s", e)
        raise ValueError(f"Invalid response format: {e}")
```

## Caching Strategy

### Types of Caching

1. **Generation Cache** - Skip already-generated content
2. **Asset Cache** - Reuse previously downloaded/generated audio/images
3. **Checkpoint Cache** - Resume from previous progress

### Benefits
- Faster iteration (don't regenerate)
- Lower API costs (fewer calls)
- Resumable pipelines

## Next Steps

Dive into [specific design patterns in action](chapter5_design_patterns.md) or 
see [code implementation examples](chapter4_code_walkthrough.md)
