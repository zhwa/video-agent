# Chapter 8 — Testing Strategies: Ensuring Reliability

This chapter covers the 76+ tests and testing patterns that ensure the code works correctly.

## Testing Philosophy

The Video Agent project has **76 comprehensive tests** covering:
- Unit tests (individual functions)
- Integration tests (multiple components)
- End-to-end tests (full pipeline)
- Concurrency tests (thread safety)
- Error handling tests (failure modes)

```
Test Coverage Hierarchy

┌─────────────────────────────────────────┐
│     End-to-End Tests (e2e)              │  Full pipeline: input → video
│  ├─ test_end_to_end_pipeline.py         │
│  └─ test_end_to_end_video.py            │
├─────────────────────────────────────────┤
│   Integration Tests                     │  Multiple components
│  ├─ test_compose_and_upload.py          │
│  ├─ test_pipeline_image_tts.py          │
│  └─ test_cli_compose.py                 │
├─────────────────────────────────────────┤
│     Unit Tests                          │  Individual functions
│  ├─ test_script_generator.py            │
│  ├─ test_video_composer.py              │
│  └─ test_segmenter.py                   │
├─────────────────────────────────────────┤
│   Specialized Tests                     │  Threading, errors, caching
│  ├─ test_concurrent_generation.py       │
│  ├─ test_error_handling.py              │
│  └─ test_cache.py                       │
└─────────────────────────────────────────┘
```

## Unit Testing Pattern

### Testing Individual Functions

```python
# tests/test_segmenter.py

import pytest
from agent.segmenter import segment_text_into_chapters

class TestSegmenter:
    
    def test_segment_simple_markdown(self):
        """Test segmenting simple markdown"""
        text = """# Chapter 1
        This is chapter 1 content.
        
        # Chapter 2
        This is chapter 2 content."""
        
        chapters = segment_text_into_chapters(text)
        
        assert len(chapters) == 2
        assert chapters[0]["title"] == "Chapter 1"
        assert chapters[1]["title"] == "Chapter 2"
        assert "Chapter 1 content" in chapters[0]["content"]
    
    def test_segment_empty_text(self):
        """Test with empty input"""
        chapters = segment_text_into_chapters("")
        assert len(chapters) == 0
    
    def test_segment_no_headers(self):
        """Test with text but no headers"""
        text = "This is just text without headers"
        chapters = segment_text_into_chapters(text)
        assert len(chapters) == 0  # No # headers means no chapters
    
    def test_segment_nested_headers(self):
        """Test with nested headers (##, ###)"""
        text = """# Chapter 1
        ## Section 1.1
        ### Subsection 1.1.1
        
        # Chapter 2
        ## Section 2.1"""
        
        chapters = segment_text_into_chapters(text)
        
        # Only top-level (# ) headers create chapters
        assert len(chapters) == 2
        assert "## Section 1.1" in chapters[0]["content"]
```

### Testing with Fixtures

```python
# tests/conftest.py - Shared fixtures

import pytest
import tempfile
import os
from agent.adapters.factory import DummyLLMAdapter

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def dummy_llm_adapter():
    """Provide dummy LLM adapter"""
    return DummyLLMAdapter()

@pytest.fixture
def sample_chapter_text():
    """Provide sample chapter text"""
    return """# Introduction to Python
    
Python is a high-level programming language. It was created by Guido van Rossum.

## Key Features

- Easy to learn
- Readable syntax
- Large standard library

## Getting Started

You can install Python from python.org."""

# Usage in tests

def test_generate_slides(dummy_llm_adapter, sample_chapter_text):
    """Test slide generation with fixtures"""
    generator = ScriptGenerator(llm_adapter=dummy_llm_adapter)
    slides = generator.generate_script(sample_chapter_text)
    
    assert "slides" in slides
    assert len(slides["slides"]) > 0
```

## Mocking External APIs

### Mocking LLM Providers

```python
# tests/test_llm_client.py

from unittest.mock import Mock, patch, MagicMock
import pytest

class TestOpenAIAdapter:
    
    def test_generate_success(self):
        """Test successful LLM call"""
        
        # Mock OpenAI client
        with patch('agent.adapters.openai_adapter.openai.OpenAI') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            
            # Setup mock response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Generated text"
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            # Test
            adapter = OpenAIAdapter(api_key="test-key")
            response = adapter.generate(LLMRequest(
                messages=[{"role": "user", "content": "test"}]
            ))
            
            assert response.text == "Generated text"
            assert response.tokens_used == 100
    
    def test_generate_rate_limit_error(self):
        """Test handling rate limit errors"""
        
        with patch('agent.adapters.openai_adapter.openai.OpenAI') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            
            # Setup mock to raise rate limit error
            import openai
            mock_client.chat.completions.create.side_effect = openai.RateLimitError("Rate limited")
            
            adapter = OpenAIAdapter(api_key="test-key")
            
            # Should raise our custom exception
            with pytest.raises(LLMRateLimitError):
                adapter.generate(LLMRequest(
                    messages=[{"role": "user", "content": "test"}]
                ))
```

### Mocking File Operations

```python
# tests/test_runs_safe.py

from unittest.mock import patch, mock_open, MagicMock
import json

class TestCheckpointManager:
    
    def test_save_checkpoint(self):
        """Test checkpoint saving with mocked file I/O"""
        
        checkpoint = SafeCheckpoint("test_run")
        
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('os.replace') as mock_replace:
                with patch('fcntl.flock') as mock_flock:
                    
                    checkpoint.save_state("node1", {"value": 42})
                    
                    # Verify file operations
                    mock_file.assert_called()
                    mock_replace.assert_called_once()
                    mock_flock.assert_called()
    
    def test_save_checkpoint_creates_directory(self):
        """Test that checkpoint dir is created"""
        
        with patch('os.makedirs') as mock_makedirs:
            checkpoint = SafeCheckpoint("test_run")
            
            mock_makedirs.assert_called_with("workspace/runs", exist_ok=True)
```

## Dummy Implementation Testing

The codebase uses dummy implementations for testing without external services:

### Dummy LLM Adapter

```python
# agent/adapters/factory.py

class DummyLLMAdapter(LLMAdapter):
    """Dummy LLM for testing without OpenAI/Vertex"""
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Return canned response"""
        return LLMResponse(
            text="This is a dummy response for testing purposes.",
            tokens_used=10,
            provider="dummy",
            model="dummy"
        )
    
    def validate_config(self) -> bool:
        return True

# Usage in tests

def test_script_generation_with_dummy_llm():
    """Test script generation without calling OpenAI"""
    generator = ScriptGenerator(llm_adapter=DummyLLMAdapter())
    
    slides = generator.generate_script("Some chapter text")
    
    # Test passes without needing API keys
    assert "slides" in slides
```

### Dummy Storage Adapter

```python
# agent/storage/dummy_storage.py

class DummyStorageAdapter(StorageAdapter):
    """In-memory storage for testing"""
    
    def __init__(self):
        self.files = {}  # In-memory file store
    
    def upload(self, local_path: str, remote_path: str) -> str:
        """Store in memory"""
        with open(local_path, 'rb') as f:
            self.files[remote_path] = f.read()
        return remote_path
    
    def download(self, remote_path: str, local_path: str) -> None:
        """Retrieve from memory"""
        if remote_path not in self.files:
            raise FileNotFoundError(remote_path)
        
        with open(local_path, 'wb') as f:
            f.write(self.files[remote_path])

# Test storage without cloud connection

def test_video_upload_with_dummy_storage():
    """Test video upload using in-memory storage"""
    storage = DummyStorageAdapter()
    
    # Upload succeeds without GCS connection
    result = storage.upload("test.mp4", "videos/test.mp4")
    
    assert result == "videos/test.mp4"
    assert "videos/test.mp4" in storage.files
```

## Integration Testing

### Testing Multiple Components

```python
# tests/test_pipeline_image_tts.py

class TestImageAndTTSPipeline:
    
    def test_generate_image_and_audio(self):
        """Test generating image and audio for a slide"""
        
        slide = {
            "id": "slide_1",
            "title": "Introduction",
            "script": "Welcome to the course",
            "image_description": "Professional office background"
        }
        
        # Generate image
        image_adapter = StabilityAdapter()
        image_path = image_adapter.generate_image(
            slide["image_description"]
        )
        assert os.path.exists(image_path)
        
        # Generate audio
        tts_adapter = ElevenLabsTTSAdapter()
        audio_path = tts_adapter.synthesize(
            slide["script"]
        )
        assert os.path.exists(audio_path)
        
        # Both should exist and be valid
        assert os.path.getsize(image_path) > 0
        assert os.path.getsize(audio_path) > 0
```

## End-to-End Testing

### Full Pipeline Test

```python
# tests/test_end_to_end_pipeline.py

class TestFullPipeline:
    
    def test_complete_pipeline_from_markdown_to_video(self):
        """Test full pipeline: markdown → slides → video"""
        
        # Input: markdown file
        input_md = "workspace/test_input.md"
        with open(input_md, 'w') as f:
            f.write("""# Chapter 1: Introduction
            
This chapter covers the basics.

# Chapter 2: Advanced Topics

Here we go deeper.""")
        
        # Run full pipeline
        result = run_full_pipeline(
            input_file=input_md,
            output_dir="workspace/test_output",
            llm_provider="dummy",
            storage_provider="dummy"
        )
        
        # Verify output
        assert result["status"] == "success"
        assert os.path.exists(result["video_path"])
        assert os.path.getsize(result["video_path"]) > 0
        assert result["chapters_processed"] == 2
        assert result["total_slides"] > 0
```

## Concurrency Testing

### Thread Safety Tests

```python
# tests/test_concurrency.py

class TestConcurrency:
    
    def test_concurrent_checkpoint_writes(self):
        """Test multiple threads writing to same checkpoint"""
        
        run_id = "concurrent_test"
        checkpoint = SafeCheckpoint(run_id)
        
        write_count = [0]
        lock = threading.Lock()
        
        def worker(thread_id):
            for i in range(50):
                checkpoint.save_state(f"node_{thread_id}_{i}", {"value": i})
                with lock:
                    write_count[0] += 1
        
        # Launch 4 threads
        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(4)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All writes should succeed (no corruption)
        assert write_count[0] == 200  # 4 threads × 50 writes
        
        # Checkpoint should be readable
        final_state = checkpoint.load_state()
        assert len(final_state) > 0
```

## Error Handling Testing

### Testing Exception Handling

```python
# tests/test_error_handling.py

class TestErrorHandling:
    
    def test_invalid_input_raises_validation_error(self):
        """Test that invalid input raises correct exception"""
        
        with pytest.raises(InputValidationError):
            validate_slide_schema({})  # Missing required fields
    
    def test_retry_on_transient_error(self):
        """Test retry mechanism for transient errors"""
        
        call_count = [0]
        
        def failing_function():
            call_count[0] += 1
            if call_count[0] < 3:
                raise LLMConnectionError("Connection failed")
            return "success"
        
        result = retry_with_backoff(failing_function, max_retries=5)
        
        assert result == "success"
        assert call_count[0] == 3  # Called 3 times
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold"""
        
        breaker = CircuitBreaker(failure_threshold=2)
        
        def failing_func():
            raise Exception("Service down")
        
        # First two calls should raise
        with pytest.raises(Exception):
            breaker.call(failing_func)
        
        with pytest.raises(Exception):
            breaker.call(failing_func)
        
        # Third call should raise CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(failing_func)
```

## Performance Testing

### Measuring Performance

```python
# tests/test_performance.py

class TestPerformance:
    
    def test_script_generation_performance(self):
        """Test that script generation completes in reasonable time"""
        
        generator = ScriptGenerator(llm_adapter=DummyLLMAdapter())
        
        chapter_text = "Sample content " * 1000  # Large text
        
        start = time.time()
        slides = generator.generate_script(chapter_text)
        elapsed = time.time() - start
        
        # Should complete within 5 seconds
        assert elapsed < 5.0
        assert len(slides["slides"]) > 0
    
    def test_concurrent_generation_throughput(self):
        """Test throughput of concurrent generation"""
        
        queue = TaskQueue(max_workers=4)
        queue.start()
        
        tasks = [
            {"type": "generate_audio", "slide": {"id": f"slide_{i}"}}
            for i in range(100)
        ]
        
        queue.submit_tasks(tasks)
        
        start = time.time()
        results = queue.wait_completion()
        elapsed = time.time() - start
        
        throughput = len(results) / elapsed
        logger.info("Throughput: %.1f tasks/second", throughput)
        
        assert throughput > 1.0  # At least 1 task per second
```

## Test Organization

```
tests/
├── conftest.py                          # Shared fixtures
├── test_adapters.py                     # Adapter tests
├── test_cache.py                        # Cache tests
├── test_cli*.py                         # CLI tests
├── test_concurrent_generation.py        # Concurrency tests
├── test_end_to_end_*.py                 # E2E tests
├── test_error_handling.py               # Error tests
├── test_langgraph_*.py                  # Graph tests
├── test_llm_client.py                   # LLM client tests
├── test_parallel_generation.py          # Parallel tests
├── test_resume_*.py                     # Resume/checkpoint tests
├── test_storage_adapter.py              # Storage tests
└── test_video_*.py                      # Video tests
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_segmenter.py -v

# Run with coverage
pytest tests/ --cov=agent --cov-report=html

# Run parallel tests only
pytest tests/ -k "concurrent" -v

# Run with output
pytest tests/ -v -s
```

## Best Practices

1. **Test one thing per test** - Single responsibility
2. **Use fixtures** - DRY principle for setup
3. **Mock external dependencies** - Don't hit real APIs in tests
4. **Test both success and failure** - Happy path and error cases
5. **Name tests clearly** - Test name describes what's being tested
6. **Test edge cases** - Empty input, None values, boundary conditions
7. **Measure performance** - Ensure no regressions
8. **Test concurrency** - Multiple threads accessing shared state

## Next Steps

Start with [hands-on exercises](chapter9_getting_started.md) to apply what you've learned
