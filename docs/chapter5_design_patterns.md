# Chapter 5 — Design Patterns: Solutions for Complex Problems

This chapter analyzes the 5+ design patterns used throughout the codebase with real examples.

## Pattern 1: Adapter Pattern

**Problem**: Need to support multiple LLM providers (OpenAI, Google Vertex, Anthropic) without rewriting code.

**Solution**: Define a common interface and implement it for each provider.

### Interface Definition: adapters/schema.py

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LLMRequest:
    """Unified request format"""
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None

@dataclass
class LLMResponse:
    """Unified response format"""
    text: str
    tokens_used: int
    provider: str
    model: str

class LLMAdapter(ABC):
    """Base class for LLM adapters"""
    
    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from messages"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Check if configuration is valid"""
        pass
```

### Implementation: OpenAI Adapter

```python
# adapters/openai_adapter.py

class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self.client = openai.OpenAI(api_key=api_key)
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self.client.chat.completions.create(
                model=request.model or self.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            return LLMResponse(
                text=response.choices[0].message.content,
                tokens_used=response.usage.total_tokens,
                provider="openai",
                model=request.model or self.model
            )
        except openai.APIError as e:
            raise LLMProviderError(f"OpenAI error: {e}")
    
    def validate_config(self) -> bool:
        try:
            self.client.models.list()
            return True
        except:
            return False
```

### Implementation: Google Vertex Adapter

```python
# adapters/google_vertex_adapter.py

class GoogleVertexAdapter(LLMAdapter):
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-1.5-pro")
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            # Convert to Vertex format
            contents = [
                Content(
                    role="user" if m["role"] == "user" else "model",
                    parts=[Part(text=m["content"])]
                )
                for m in request.messages
            ]
            
            response = self.model.generate_content(
                contents=contents,
                generation_config=GenerationConfig(
                    temperature=request.temperature,
                    max_output_tokens=request.max_tokens
                )
            )
            
            return LLMResponse(
                text=response.text,
                tokens_used=response.usage_metadata.total_token_count,
                provider="google",
                model="gemini-1.5-pro"
            )
        except Exception as e:
            raise LLMProviderError(f"Vertex AI error: {e}")
    
    def validate_config(self) -> bool:
        try:
            self.model.generate_content("test")
            return True
        except:
            return False
```

### Usage: Adapter Factory

```python
# adapters/factory.py

def get_llm_adapter(provider: str, config: Dict) -> LLMAdapter:
    """Factory function to create adapters"""
    
    if provider == "openai":
        return OpenAIAdapter(
            api_key=config["api_key"],
            model=config.get("model", "gpt-4")
        )
    
    elif provider == "vertex":
        return GoogleVertexAdapter(
            project_id=config["project_id"],
            location=config.get("location", "us-central1")
        )
    
    elif provider == "dummy":
        return DummyAdapter()
    
    else:
        raise ValueError(f"Unknown provider: {provider}")

def validate_provider_config(provider: str, config: Dict) -> bool:
    """Validate provider configuration"""
    adapter = get_llm_adapter(provider, config)
    return adapter.validate_config()
```

**Benefits**:
- Add new LLM providers without changing existing code
- Swap providers at runtime
- Test with dummy implementation
- Consistent error handling

---

## Pattern 2: Factory Pattern with Dependency Injection

**Problem**: Creating adapters requires configuration that changes per environment.

**Solution**: Use factory functions to centralize object creation.

### Factory Implementation

```python
# adapters/factory.py

_adapters = {}

def register_adapter(name: str, adapter: LLMAdapter) -> None:
    """Register an adapter implementation"""
    _adapters[name] = adapter

def get_llm_adapter(name: str = None) -> LLMAdapter:
    """Get adapter by name or return default"""
    if name is None:
        name = os.environ.get("LLM_PROVIDER", "dummy")
    
    if name not in _adapters:
        raise ValueError(f"Unknown adapter: {name}")
    
    return _adapters[name]

# Initialization at startup

def initialize_adapters(config: Dict) -> None:
    """Initialize all adapters from configuration"""
    
    # OpenAI
    if "openai" in config:
        openai_adapter = OpenAIAdapter(**config["openai"])
        register_adapter("openai", openai_adapter)
    
    # Vertex
    if "vertex" in config:
        vertex_adapter = GoogleVertexAdapter(**config["vertex"])
        register_adapter("vertex", vertex_adapter)
    
    # Dummy (always available)
    register_adapter("dummy", DummyAdapter())
    
    logger.info("Initialized adapters: %s", list(_adapters.keys()))
```

### Configuration File

```yaml
# config/providers.yaml

llm:
  openai:
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
  vertex:
    project_id: ${GOOGLE_PROJECT_ID}
    location: us-central1

embeddings:
  openai:
    api_key: ${OPENAI_API_KEY}
    model: text-embedding-3-large

tts:
  elevenlabs:
    api_key: ${ELEVENLABS_API_KEY}
    voice_id: 21m00Tcm4TlvDq8ikWAM

storage:
  gcs:
    project_id: ${GOOGLE_PROJECT_ID}
    bucket: video-agent-output
```

---

## Pattern 3: Retry Pattern with Exponential Backoff

**Problem**: LLM APIs fail occasionally; we need resilience.

**Solution**: Automatically retry with increasing delays.

### Implementation

```python
# llm_client.py

def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0
) -> Any:
    """Retry function with exponential backoff"""
    
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            logger.debug("Attempt %d/%d", attempt + 1, max_retries)
            return func()
        
        except (APIConnectionError, RateLimitError) as e:
            # Transient error - retry
            if attempt < max_retries - 1:
                logger.warning(
                    "Attempt %d failed with transient error: %s. "
                    "Retrying in %f seconds",
                    attempt + 1, e, delay
                )
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error("Max retries exceeded")
                raise
        
        except (ValueError, KeyError) as e:
            # Permanent error - don't retry
            logger.error("Permanent error: %s", e)
            raise
    
    return None

# Decorator version

def retry(max_retries: int = 3, initial_delay: float = 1.0):
    """Decorator for retry logic"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_with_backoff(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                initial_delay=initial_delay
            )
        return wrapper
    
    return decorator

# Usage

@retry(max_retries=3, initial_delay=2.0)
def generate_slides(chapter_text: str) -> Dict:
    """Generate slides with automatic retry"""
    adapter = get_llm_adapter()
    return adapter.generate(chapter_text)
```

**Backoff Formula**:
- Attempt 1: Immediate
- Attempt 2: After 1 second
- Attempt 3: After 2 seconds  
- Attempt 4: After 4 seconds
- Attempt 5: After 8 seconds

**Benefits**:
- Handles transient failures automatically
- Avoids overwhelming APIs
- Distinguishes transient vs permanent errors
- Configurable retry policy

---

## Pattern 4: Thread-Safe State Management

**Problem**: Multiple threads accessing shared state causes race conditions.

**Solution**: Use file locking and atomic operations.

### File Locking

```python
# runs_safe.py

import fcntl
import tempfile

class CheckpointManager:
    def __init__(self, checkpoint_dir: str = "workspace/runs"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)
    
    def save_checkpoint(self, run_id: str, node: str, data: Dict) -> None:
        """Thread-safe checkpoint save with locking"""
        lock_path = os.path.join(self.checkpoint_dir, f"{run_id}.lock")
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{run_id}.json")
        
        logger.debug("Acquiring lock for %s", run_id)
        
        # Acquire lock
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o666)
        
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)  # Exclusive lock
            logger.debug("Lock acquired")
            
            # Read current state
            current = {}
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path) as f:
                    current = json.load(f)
            
            # Update state
            current[node] = data
            current["updated_at"] = datetime.utcnow().isoformat()
            
            # Write atomically using temp file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.checkpoint_dir
            )
            
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(current, f)
                
                # Atomic rename
                os.replace(temp_path, checkpoint_path)
                logger.debug("Checkpoint saved atomically")
            
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            logger.debug("Lock released")
    
    def load_checkpoint(self, run_id: str) -> Dict:
        """Thread-safe checkpoint load"""
        checkpoint_path = os.path.join(self.checkpoint_dir, f"{run_id}.json")
        
        logger.debug("Loading checkpoint: %s", run_id)
        
        if not os.path.exists(checkpoint_path):
            logger.warning("Checkpoint not found: %s", run_id)
            return {}
        
        with open(checkpoint_path) as f:
            data = json.load(f)
        
        logger.debug("Checkpoint loaded: %d bytes", len(json.dumps(data)))
        return data
```

**Key Techniques**:
- Exclusive file lock (fcntl.LOCK_EX)
- Temp file + atomic rename
- Lock release in finally block
- Timeout handling

---

## Pattern 5: Rate Limiting (Token Bucket)

**Problem**: APIs have rate limits; need to throttle requests.

**Solution**: Token bucket algorithm - tokens accumulate, each request consumes tokens.

### Implementation

```python
# parallel.py

import time
from threading import Lock

class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: float, burst: int = 1):
        """
        rate: tokens per second
        burst: maximum tokens in bucket
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self.lock = Lock()
    
    def wait_if_needed(self) -> None:
        """Block until token available"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(
                self.burst,
                self.tokens + elapsed * self.rate
            )
            
            self.last_update = now
            
            # If no tokens, wait
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                logger.debug("Rate limit: sleeping %.2f seconds", wait_time)
                time.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

# Usage

def run_tasks_with_rate_limit(
    tasks: List[Dict],
    requests_per_second: float = 10.0
) -> List:
    """Run tasks with rate limiting"""
    limiter = RateLimiter(rate=requests_per_second)
    
    results = []
    for task in tasks:
        limiter.wait_if_needed()
        result = execute_task(task)
        results.append(result)
    
    return results
```

**Example**:
- Rate: 10 requests/second (100ms per request)
- Burst: 5 (allow 5 requests immediately, then throttle)
- After 500ms: 5 new tokens available

---

## Pattern 6: Graceful Degradation

**Problem**: If an external service fails, crash the whole pipeline.

**Solution**: Provide fallback implementations.

### Dummy Implementations

```python
# adapters/factory.py

class DummyLLMAdapter(LLMAdapter):
    """Fallback LLM adapter for testing/fallback"""
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        # Return canned response
        return LLMResponse(
            text="This is a dummy response for testing purposes.",
            tokens_used=10,
            provider="dummy",
            model="dummy"
        )
    
    def validate_config(self) -> bool:
        return True

class DummyTTSAdapter(TTSAdapter):
    """Fallback TTS adapter"""
    
    def synthesize(self, text: str, voice_id: str = "default") -> bytes:
        # Generate silence or simple tone
        import numpy as np
        
        sample_rate = 16000
        duration = 1  # 1 second
        samples = np.zeros(sample_rate * duration, dtype=np.int16)
        
        return samples.tobytes()

# Fallback strategy

def get_llm_adapter_with_fallback(
    provider: str = None
) -> LLMAdapter:
    """Get adapter, fallback to dummy if unavailable"""
    
    try:
        adapter = get_llm_adapter(provider)
        if adapter.validate_config():
            return adapter
    except Exception as e:
        logger.warning("Failed to initialize %s adapter: %s", provider, e)
    
    logger.info("Falling back to dummy adapter")
    return DummyLLMAdapter()
```

---

## Summary of Patterns

| Pattern | Problem | Solution | Example |
|---------|---------|----------|---------|
| Adapter | Multiple implementations | Common interface | LLM providers |
| Factory | Complex creation | Centralized construction | adapter factory |
| Retry | Transient failures | Auto-retry with backoff | LLM calls |
| Thread-safe | Race conditions | File locking + atomic ops | checkpoints |
| Rate limiting | API throttling | Token bucket | parallel tasks |
| Graceful degradation | Service failure | Fallback implementations | dummy adapters |

Each pattern addresses a real problem in the codebase and is applied consistently.

## Next Steps

Learn how [errors are handled systematically](chapter6_error_handling.md) or
explore [concurrency and threading](chapter7_concurrency.md)
