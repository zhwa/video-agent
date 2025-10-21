# Chapter 9 — Getting Started: Hands-On Exercises

This chapter provides practical exercises to apply the concepts from previous chapters.

## Before You Start

Make sure you have:
- Python 3.11+
- Git
- The Video Agent repository cloned
- All tests passing (`pytest tests/ -v`)

## Exercise 1: Add a New LLM Provider

**Objective**: Implement a new LLM adapter for Anthropic Claude.

**Why**: Practice the Adapter and Factory patterns.

**Difficulty**: ⭐⭐ (Intermediate)

### Instructions

1. **Create the adapter file**: `agent/adapters/anthropic_adapter.py`

```python
from agent.adapters.schema import LLMAdapter, LLMRequest, LLMResponse
import anthropic

class AnthropicAdapter(LLMAdapter):
    """LLM adapter for Anthropic Claude"""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus"):
        self.api_key = api_key
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using Claude"""
        # TODO: Implement
        # 1. Convert request.messages to Anthropic format
        # 2. Call self.client.messages.create()
        # 3. Return LLMResponse with response.content[0].text
        pass
    
    def validate_config(self) -> bool:
        """Check if API key is valid"""
        # TODO: Implement
        # Try making a simple API call to validate
        pass
```

2. **Register the adapter** in `agent/adapters/factory.py`:

```python
def initialize_adapters(config: Dict) -> None:
    """Initialize all adapters from configuration"""
    
    # ... existing code ...
    
    # Anthropic
    if "anthropic" in config:
        anthropic_adapter = AnthropicAdapter(**config["anthropic"])
        register_adapter("anthropic", anthropic_adapter)
```

3. **Write a test**: `tests/test_anthropic_adapter.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from agent.adapters.anthropic_adapter import AnthropicAdapter
from agent.adapters.schema import LLMRequest

class TestAnthropicAdapter:
    
    def test_generate_success(self):
        """Test successful Claude generation"""
        # TODO: Mock anthropic client and test generate()
        pass
    
    def test_validate_config_success(self):
        """Test config validation"""
        # TODO: Test validate_config()
        pass
```

4. **Update configuration**: `config/providers.example.yaml`

```yaml
llm:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-opus
```

5. **Verify it works**:

```bash
export ANTHROPIC_API_KEY=your-key-here
pytest tests/test_anthropic_adapter.py -v
```

### Solution Hints

- Look at `agent/adapters/openai_adapter.py` for reference
- Anthropic uses `messages.create()` instead of `chat.completions.create()`
- Convert OpenAI format messages to Anthropic format (same structure)
- Test with both mock and real API

---

## Exercise 2: Implement Retry Logic with Exponential Backoff

**Objective**: Add automatic retry to a function.

**Why**: Practice the Retry pattern and error handling.

**Difficulty**: ⭐⭐ (Intermediate)

### Instructions

1. **Create a retry decorator**: `agent/retry.py`

```python
import time
import functools
import logging
from typing import Callable, Type, Tuple

logger = logging.getLogger(__name__)

def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable = None
):
    """Decorator to retry a function with exponential backoff
    
    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiply delay by this after each failure
        exceptions: Only retry on these exception types
        on_retry: Optional callback when retrying
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # TODO: Implement retry logic
            # 1. Loop up to max_attempts times
            # 2. Try calling func(*args, **kwargs)
            # 3. On exception:
            #    - If in exceptions tuple: log and retry
            #    - If not: raise immediately
            # 4. Calculate delay with exponential backoff
            # 5. Call on_retry callback if provided
            # 6. Sleep before next attempt
            pass
        
        return wrapper
    
    return decorator
```

2. **Use the decorator**: `agent/script_generator.py`

```python
@retry(
    max_attempts=3,
    initial_delay=2.0,
    exceptions=(LLMRateLimitError, LLMConnectionError)
)
def generate_slides_with_retry(self, chapter_text: str) -> Dict:
    """Generate slides with automatic retry"""
    adapter = get_llm_adapter()
    return adapter.generate(chapter_text)
```

3. **Write tests**: `tests/test_retry_decorator.py`

```python
import pytest
import time
from agent.retry import retry

class TestRetry:
    
    def test_retry_succeeds_on_second_attempt(self):
        """Test that function succeeds after retry"""
        attempt_count = [0]
        
        @retry(max_attempts=3, initial_delay=0.1)
        def failing_function():
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise RuntimeError("Failed")
            return "success"
        
        result = failing_function()
        
        assert result == "success"
        assert attempt_count[0] == 2  # Called twice
    
    def test_retry_respects_max_attempts(self):
        """Test that function stops after max attempts"""
        # TODO: Test that exception is raised after max_attempts
        pass
    
    def test_retry_with_backoff_delay(self):
        """Test that delay increases exponentially"""
        # TODO: Measure time and verify backoff
        pass
    
    def test_retry_only_certain_exceptions(self):
        """Test that only specified exceptions trigger retry"""
        # TODO: Test that other exceptions are raised immediately
        pass
```

### Solution Hints

- Use `time.time()` to measure elapsed time
- Calculate delay as `initial_delay * (backoff_factor ** attempt)`
- Add small random jitter to prevent thundering herd
- Log at WARNING level when retrying

---

## Exercise 3: Add Error Handling to Video Composition

**Objective**: Add comprehensive error handling to video composition.

**Why**: Practice error handling and testing error paths.

**Difficulty**: ⭐⭐⭐ (Advanced)

### Instructions

1. **Create error tests**: `tests/test_video_composer_errors.py`

```python
import pytest
from agent.video_composer import VideoComposer
from agent.exceptions import (
    VideoCompositionError,
    AudioFileNotFoundError,
    ImageFileNotFoundError
)

class TestVideoComposerErrors:
    
    def test_compose_with_missing_image(self, temp_dir):
        """Test that missing image raises proper error"""
        
        composer = VideoComposer()
        slides = [
            {
                "slide_number": 1,
                "image_path": "/nonexistent/image.png",  # Doesn't exist
                "audio_path": "audio.mp3"
            }
        ]
        
        with pytest.raises(ImageFileNotFoundError):
            composer.compose_chapter_video(slides, f"{temp_dir}/output.mp4")
    
    def test_compose_with_invalid_audio(self, temp_dir):
        """Test that invalid audio raises proper error"""
        
        # TODO: Implement
        pass
    
    def test_compose_recovers_from_partial_failure(self, temp_dir):
        """Test graceful handling of partial failures"""
        
        # TODO: Implement
        pass
```

2. **Improve `video_composer.py`**:

```python
from agent.exceptions import (
    VideoCompositionError,
    ImageFileNotFoundError,
    AudioFileNotFoundError
)

class VideoComposer:
    
    def compose_chapter_video(self, slides: List[Dict], output_path: str) -> Dict:
        """Compose video with comprehensive error handling"""
        
        logger.info("Composing video with %d slides", len(slides))
        
        try:
            # Validate all files exist before starting
            self._validate_input_files(slides)
            
            clips = []
            
            for slide in slides:
                try:
                    clip = self._create_slide_clip(slide)
                    clips.append(clip)
                
                except (ImageFileNotFoundError, AudioFileNotFoundError) as e:
                    logger.warning("Skipping slide: %s", e)
                    # Continue with other slides
                    continue
            
            if not clips:
                raise VideoCompositionError("No valid slides to compose")
            
            # Compose and write
            video = concatenate_videoclips(clips)
            video.write_videofile(output_path, fps=24)
            
            return {"video_path": output_path, "slides": len(clips)}
        
        except VideoCompositionError:
            raise  # Re-raise our exceptions
        
        except Exception as e:
            logger.error("Composition failed: %s", e, exc_info=True)
            raise VideoCompositionError(f"Composition failed: {e}") from e
    
    def _validate_input_files(self, slides: List[Dict]) -> None:
        """Validate all input files exist"""
        
        for slide in slides:
            image_path = slide.get("image_path")
            audio_path = slide.get("audio_path")
            
            if image_path and not os.path.exists(image_path):
                raise ImageFileNotFoundError(f"Image not found: {image_path}")
            
            if audio_path and not os.path.exists(audio_path):
                raise AudioFileNotFoundError(f"Audio not found: {audio_path}")
```

3. **Add the exception classes**: `agent/exceptions.py`

```python
class VideoCompositionError(VideoAgentError):
    """Video composition failed"""
    pass

class ImageFileNotFoundError(VideoCompositionError):
    """Image file not found"""
    pass

class AudioFileNotFoundError(VideoCompositionError):
    """Audio file not found"""
    pass
```

### Solution Hints

- Validate all inputs before starting expensive operations
- Continue processing when possible (skip bad slides)
- Provide clear error messages about what failed
- Test both happy path and error paths

---

## Exercise 4: Implement Thread-Safe Checkpoint Resumption

**Objective**: Ensure checkpoints work correctly with multiple threads.

**Why**: Practice concurrency, thread-safety, and testing.

**Difficulty**: ⭐⭐⭐ (Advanced)

### Instructions

1. **Write concurrency tests**: `tests/test_checkpoint_concurrent.py`

```python
import threading
import pytest
from agent.runs_safe import SafeCheckpoint

class TestCheckpointConcurrency:
    
    def test_concurrent_writes_no_corruption(self):
        """Test that concurrent writes don't corrupt state"""
        
        checkpoint = SafeCheckpoint("concurrent_test")
        results = []
        
        def worker(worker_id: int):
            for i in range(100):
                data = {"worker_id": worker_id, "iteration": i}
                checkpoint.save_state(f"node_{worker_id}_{i}", data)
                results.append((worker_id, i))
        
        # Launch 4 workers
        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(4)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All writes should succeed
        assert len(results) == 400
        
        # State should be readable
        state = checkpoint.load_state()
        assert len(state) >= 100  # At least 100 nodes
        
        # Verify no corruption
        for node_name, node_data in state.items():
            if node_name != "updated_at":
                assert isinstance(node_data, dict)
    
    def test_write_while_reading(self):
        """Test concurrent read/write"""
        
        # TODO: Implement test
        pass
    
    def test_resume_from_concurrent_checkpoint(self):
        """Test that checkpoint can be resumed after concurrent writes"""
        
        # TODO: Implement test
        pass
```

2. **Improve checkpoint resumption**: `agent/runs_safe.py`

```python
def resume_from_checkpoint(run_id: str) -> Dict:
    """Resume execution from last checkpoint"""
    
    checkpoint = SafeCheckpoint(run_id)
    state = checkpoint.load_state()
    
    if not state:
        logger.info("No checkpoint found for %s, starting fresh", run_id)
        return {}
    
    logger.info("Resuming from checkpoint: %d nodes", len(state))
    
    # Validate checkpoint integrity
    try:
        _validate_checkpoint_structure(state)
    except ValueError as e:
        logger.error("Checkpoint corrupted: %s", e)
        raise CheckpointError(f"Cannot resume: {e}")
    
    return state

def _validate_checkpoint_structure(state: Dict) -> None:
    """Validate checkpoint has expected structure"""
    
    if not isinstance(state, dict):
        raise ValueError("Checkpoint is not a dict")
    
    # Check required fields
    if "updated_at" not in state:
        raise ValueError("Missing updated_at field")
    
    # Check node structure
    for key, value in state.items():
        if key == "updated_at":
            continue
        
        if not isinstance(value, dict):
            raise ValueError(f"Invalid node structure: {key}")
```

### Solution Hints

- Use threading locks for test coordination
- Verify no file corruption after concurrent writes
- Test both success and failure paths
- Add validation to detect corrupted state early

---

## Exercise 5: Create a Custom Validation Schema

**Objective**: Add validation for video metadata.

**Why**: Practice validation patterns and testing.

**Difficulty**: ⭐ (Beginner)

### Instructions

1. **Create schema**: `agent/schemas.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class VideoMetadata(BaseModel):
    """Metadata for generated video"""
    
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    duration_seconds: float = Field(..., gt=0)
    chapters: int = Field(..., ge=1)
    slides_per_chapter: int = Field(..., ge=1)
    
    @validator('title')
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be blank")
        return v.strip()
    
    @validator('description')
    def description_not_offensive(cls, v):
        # Could check against word list
        if v and len(v) < 3:
            raise ValueError("Description too short")
        return v

# Usage in tests

def test_valid_metadata():
    """Test valid metadata"""
    meta = VideoMetadata(
        title="My Video",
        description="A great video",
        duration_seconds=300,
        chapters=3,
        slides_per_chapter=10
    )
    assert meta.title == "My Video"

def test_invalid_metadata():
    """Test invalid metadata raises error"""
    with pytest.raises(ValidationError):
        VideoMetadata(
            title="",  # Empty title
            duration_seconds=300,
            chapters=3,
            slides_per_chapter=10
        )
```

2. **Integrate into composer**: `agent/video_composer.py`

```python
def compose_chapter_video(
    self,
    slides: List[Dict],
    output_path: str,
    metadata: VideoMetadata = None
) -> Dict:
    """Compose video with validated metadata"""
    
    if metadata:
        # Validation happens automatically
        logger.info("Video metadata: title=%s, duration=%.1f", 
                   metadata.title, metadata.duration_seconds)
    
    # ... rest of composition ...
```

---

## Assessment

### Completion Checklist

- [ ] Exercise 1: New LLM adapter implemented and tested
- [ ] Exercise 2: Retry decorator working with tests
- [ ] Exercise 3: Error handling comprehensive and tested
- [ ] Exercise 4: Checkpoint concurrency verified
- [ ] Exercise 5: Validation schema created

### Self-Assessment Rubric

**Excellent** (90-100%):
- All exercises completed
- All tests passing (76+ tests)
- Code follows patterns from codebase
- Error handling comprehensive
- Clear logging and comments

**Good** (80-89%):
- 4-5 exercises completed
- Tests passing with minor issues
- Code reasonably follows patterns
- Basic error handling
- Some logging

**Satisfactory** (70-79%):
- 3-4 exercises completed
- Some test failures
- Code structure reasonable
- Minimal error handling
- Limited logging

**Needs Improvement** (<70%):
- Fewer than 3 exercises completed
- Multiple test failures
- Code doesn't follow patterns
- Inadequate error handling

---

## Next Steps After Exercises

1. **Review**: Look at similar implementations in the codebase
2. **Refactor**: Apply lessons to improve your code
3. **Test**: Run full test suite: `pytest tests/ -v`
4. **Deploy**: Try running with your changes
5. **Learn**: Study the code you wrote and patterns used

## Advanced Topics to Explore

1. **Distributed Caching**: How to cache results across processes
2. **Performance Optimization**: Profile and optimize slow paths
3. **Observability**: Add metrics and tracing
4. **Security**: Add input sanitization and auth
5. **Scalability**: Adapt for high-volume production use

## Getting Help

1. **Tests are your documentation**: Read tests to understand how things work
2. **Review similar code**: Find similar pattern in codebase and copy
3. **Check logs**: Enable debug logging to see what's happening
4. **Run incrementally**: Test your code as you write it

## Final Project Ideas

1. **Audio Trimming**: Add voice-over duration matching
2. **Multi-Language Support**: Generate videos in different languages
3. **Custom Themes**: Apply different visual styles to videos
4. **Analytics Dashboard**: Track video generation metrics
5. **API Server**: Expose Video Agent as REST API

---

## Congratulations!

You've learned the Video Agent architecture, design patterns, error handling, concurrency, and testing strategies. Apply these lessons to build robust production systems!

### Key Takeaways

✅ **Adapter Pattern**: Swap implementations without changing code
✅ **Retry Pattern**: Handle transient failures gracefully
✅ **Error Handling**: Specific exceptions, clear messages, recovery
✅ **Concurrency**: File locking, queues, thread-local storage
✅ **Testing**: Unit, integration, E2E, and concurrency tests
✅ **Code Quality**: 76/76 tests, logging, validation, documentation

### Resources

- See Chapter 1 for learning path overview
- See Chapter 2 for architecture details
- See Chapter 3 for design patterns
- See Chapter 4 for code walkthrough
- See Chapter 5 for pattern deep dives
- See Chapter 6 for error handling details
- See Chapter 7 for concurrency details
- See Chapter 8 for testing patterns
