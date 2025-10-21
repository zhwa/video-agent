# Chapter 6 — Error Handling & Logging: Production Reliability

This chapter covers the comprehensive error handling and logging strategy that makes the system reliable and observable.

## Exception Hierarchy

The codebase defines 50+ specific exception types for precise error handling:

### Base Exceptions

```python
# agent/schema.py

class VideoAgentError(Exception):
    """Base exception for all Video Agent errors"""
    pass

class ConfigurationError(VideoAgentError):
    """Configuration is invalid"""
    pass

class LLMProviderError(VideoAgentError):
    """LLM provider failure"""
    pass

class ResourceError(VideoAgentError):
    """Resource not available"""
    pass

class ValidationError(VideoAgentError):
    """Data validation failed"""
    pass
```

### Specific Exceptions

```python
# LLM-related exceptions

class LLMConnectionError(LLMProviderError):
    """Cannot connect to LLM provider"""
    pass

class LLMRateLimitError(LLMProviderError):
    """Rate limit exceeded"""
    pass

class LLMAuthError(LLMProviderError):
    """Authentication failed"""
    pass

class LLMResponseError(LLMProviderError):
    """Invalid response from LLM"""
    pass

# Media-related exceptions

class AudioGenerationError(VideoAgentError):
    """TTS generation failed"""
    pass

class ImageGenerationError(VideoAgentError):
    """Image generation failed"""
    pass

class VideoCompositionError(VideoAgentError):
    """Video composition failed"""
    pass

class VideoUploadError(VideoAgentError):
    """Video upload failed"""
    pass

# Storage-related exceptions

class StorageError(ResourceError):
    """Storage operation failed"""
    pass

class StorageConnectionError(StorageError):
    """Cannot connect to storage"""
    pass

class StoragePermissionError(StorageError):
    """Permission denied on storage"""
    pass

# Validation exceptions

class InputValidationError(ValidationError):
    """Input data is invalid"""
    pass

class SchemaValidationError(ValidationError):
    """Data doesn't match schema"""
    pass

class ChecksumValidationError(ValidationError):
    """Checksum mismatch"""
    pass
```

## Error Handling Strategies

### Strategy 1: Layered Error Handling

Errors are caught at different levels:

```python
# Level 1: In adapters (convert provider errors)

class OpenAIAdapter(LLMAdapter):
    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self.client.chat.completions.create(...)
            return LLMResponse(...)
        except openai.RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit: {e}") from e
        except openai.AuthenticationError as e:
            raise LLMAuthError(f"OpenAI auth failed: {e}") from e
        except openai.APIConnectionError as e:
            raise LLMConnectionError(f"OpenAI connection failed: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"OpenAI error: {e}") from e

# Level 2: In business logic (catch specific errors, retry if appropriate)

class ScriptGenerator:
    def generate_script(self, chapter_text: str) -> Dict:
        try:
            adapter = get_llm_adapter()
            response = adapter.generate(chapter_text)
            return parse_response(response)
        
        except LLMRateLimitError as e:
            logger.warning("Rate limited, waiting before retry: %s", e)
            time.sleep(60)  # Wait 1 minute
            return self.generate_script(chapter_text)  # Retry
        
        except LLMAuthError as e:
            logger.error("Authentication failed: %s", e)
            raise  # Don't retry - configuration error
        
        except Exception as e:
            logger.error("Script generation failed: %s", e)
            raise

# Level 3: In CLI (catch all, display user-friendly message)

def main():
    try:
        result = run_pipeline(args)
        logger.info("Pipeline completed successfully")
    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        print("ERROR: Invalid configuration - see log for details")
        sys.exit(1)
    except LLMProviderError as e:
        logger.error("LLM provider error: %s", e)
        print("ERROR: LLM provider unavailable - check API key and connection")
        sys.exit(2)
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        print("ERROR: Unexpected failure - see log for details")
        sys.exit(3)
```

### Strategy 2: Error Context and Recovery

```python
# Include context in exceptions

class OperationError(VideoAgentError):
    def __init__(self, message: str, context: Dict = None):
        super().__init__(message)
        self.context = context or {}

# Capture context at error point

def save_checkpoint(run_id: str, node: str, data: Dict):
    try:
        lock_file = get_lock_path(run_id)
        _acquire_lock(lock_file)
        
        checkpoint_file = get_checkpoint_path(run_id)
        with open(checkpoint_file, 'w') as f:
            json.dump(data, f)
    
    except IOError as e:
        context = {
            "run_id": run_id,
            "node": node,
            "checkpoint_file": checkpoint_file
        }
        raise StorageError(
            f"Failed to save checkpoint: {e}",
            context=context
        ) from e

# Recover from error

def load_or_create_checkpoint(run_id: str) -> Dict:
    try:
        return load_checkpoint(run_id)
    except StorageError as e:
        logger.warning("Failed to load checkpoint: %s", e)
        logger.info("Starting fresh for run: %s", run_id)
        return {}
```

## Structured Logging

### Log Levels

```python
# DEBUG: Detailed debugging info
logger.debug("Rate limiter: sleeping %.2f seconds", wait_time)
logger.debug("Acquiring lock for checkpoint")
logger.debug("LLM response: %s", response[:100])

# INFO: High-level progress
logger.info("Segmented %d chapters", len(chapters))
logger.info("Generated %d slides", len(slides))
logger.info("Composed video: %s", output_path)
logger.info("Pipeline completed successfully")

# WARNING: Something unexpected happened
logger.warning("Missing image or audio for slide %s", slide["slide_number"])
logger.warning("Failed to load checkpoint: %s", e)
logger.warning("Attempt %d failed with transient error: %s", attempt, e)

# ERROR: Something failed
logger.error("Video composition failed: %s", e)
logger.error("Script generation failed: %s", e)
logger.error("Pipeline failed: %s", e)

# CRITICAL: System is in bad state
logger.critical("Configuration file not found: %s", config_file)
```

### Structured Logging Pattern

```python
# Include context in all logs

def generate_slides(chapter_id: str, chapter_text: str) -> Dict:
    logger.info(
        "Generating slides",
        extra={
            "chapter_id": chapter_id,
            "text_length": len(chapter_text),
            "operation": "generate_slides"
        }
    )
    
    start_time = time.time()
    
    try:
        slides = _generate_slides(chapter_text)
        
        duration = time.time() - start_time
        logger.info(
            "Slides generated successfully",
            extra={
                "chapter_id": chapter_id,
                "slide_count": len(slides),
                "duration_seconds": duration,
                "operation": "generate_slides"
            }
        )
        
        return slides
    
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "Slide generation failed",
            extra={
                "chapter_id": chapter_id,
                "duration_seconds": duration,
                "error": str(e),
                "operation": "generate_slides"
            },
            exc_info=True
        )
        raise
```

### Logging Configuration

```python
# agent/telemetry.py

import logging
import logging.config
import json

def configure_logging(log_dir: str = "workspace/llm_logs", level=logging.INFO):
    """Configure structured logging"""
    
    os.makedirs(log_dir, exist_ok=True)
    
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "verbose",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "json",
                "filename": os.path.join(log_dir, "agent.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5
            }
        },
        "root": {
            "level": level,
            "handlers": ["console", "file"]
        }
    }
    
    logging.config.dictConfig(config)
    logger = logging.getLogger(__name__)
    logger.info("Logging configured: level=%s, log_dir=%s", level, log_dir)
    
    return logger
```

## Error Recovery Patterns

### Pattern 1: Retry with Exponential Backoff

```python
def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True
) -> Any:
    """Retry with exponential backoff and optional jitter"""
    
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            return func()
        
        except Exception as e:
            if attempt < max_retries - 1:
                # Calculate delay with optional jitter
                actual_delay = delay
                if jitter:
                    import random
                    actual_delay += random.uniform(0, delay * 0.1)
                
                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.2f seconds",
                    attempt + 1, max_retries, e, actual_delay
                )
                
                time.sleep(actual_delay)
                delay *= backoff_factor
            else:
                logger.error("Max retries (%d) exceeded", max_retries)
                raise
```

### Pattern 2: Fallback to Dummy Implementation

```python
def get_adapter_with_fallback(provider: str) -> Adapter:
    """Get adapter or fallback to dummy"""
    
    try:
        adapter = get_llm_adapter(provider)
        
        # Validate it works
        if not adapter.validate_config():
            raise ConfigurationError(f"Adapter validation failed: {provider}")
        
        logger.info("Using adapter: %s", provider)
        return adapter
    
    except Exception as e:
        logger.warning(
            "Failed to initialize %s adapter: %s. Using dummy.",
            provider, e
        )
        return DummyAdapter()
```

### Pattern 3: Circuit Breaker

```python
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function with circuit breaker protection"""
        
        if self.state == CircuitState.OPEN:
            # Check if we should try recovery
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
                logger.info("Circuit breaker attempting reset")
            else:
                raise CircuitBreakerOpen("Circuit is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _on_success(self):
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker closed after recovery")
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error("Circuit breaker opened after %d failures", self.failure_count)
```

## Testing Error Handling

```python
# tests/test_error_handling.py

def test_retry_with_backoff():
    """Test retry mechanism"""
    call_count = [0]
    
    def failing_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise LLMConnectionError("Connection failed")
        return "success"
    
    result = retry_with_backoff(failing_func, max_retries=3)
    assert result == "success"
    assert call_count[0] == 3  # Called 3 times

def test_fallback_to_dummy():
    """Test fallback mechanism"""
    adapter = get_adapter_with_fallback("invalid_provider")
    assert isinstance(adapter, DummyAdapter)

def test_circuit_breaker():
    """Test circuit breaker"""
    breaker = CircuitBreaker(failure_threshold=2)
    
    def failing_func():
        raise Exception("Service down")
    
    # First two failures
    with pytest.raises(Exception):
        breaker.call(failing_func)
    
    with pytest.raises(Exception):
        breaker.call(failing_func)
    
    # Circuit should be open now
    with pytest.raises(CircuitBreakerOpen):
        breaker.call(failing_func)

def test_error_context():
    """Test error context capture"""
    try:
        raise OperationError(
            "Operation failed",
            context={"run_id": "test123", "step": "generation"}
        )
    except OperationError as e:
        assert e.context["run_id"] == "test123"
```

## Best Practices

1. **Use specific exceptions**: Never catch `Exception`; catch specific error types
2. **Preserve error context**: Use `raise ... from e` to maintain stack traces
3. **Log before raising**: Include context about what was happening
4. **Clean up in finally**: Always release resources in finally blocks
5. **Test error paths**: Error handling code needs testing too
6. **Monitor in production**: Log all errors with context for debugging

## Next Steps

Learn about [concurrency challenges and solutions](chapter7_concurrency.md) or
explore [testing strategies for production code](chapter8_testing_strategies.md)
