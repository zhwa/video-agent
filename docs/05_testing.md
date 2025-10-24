# Chapter 5: Testing

Comprehensive testing guide for Video Agent, covering test strategies, frameworks, and best practices.

---

## Testing Overview

### Test Structure

Video Agent uses **pytest** with comprehensive coverage:

- **45 passing tests** across all components
- **12 skipped tests** (require Google API key)
- **~95% code coverage** on core modules

**Test Distribution**:
```
Unit Tests (60%)
├── Script Generator
├── Video Composer
├── LLM Client
├── Cache System
└── Google Services

Integration Tests (30%)
├── End-to-end Pipeline
├── Resume/Checkpoint
└── Google API Integration

System Tests (10%)
├── CLI Tests
├── Full Pipeline
└── Parallel Processing
```

---

## Running Tests

### Quick Start

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_script_generator.py -v

# Run single test
python -m pytest tests/test_script_generator.py::test_generate_slides -v
```

### Test Filters

```bash
# Run fast tests only (skip slow/heavy tests)
python -m pytest -m "not slow"

# Run tests by keyword
python -m pytest -k "cache" -v

# Run with specific marker
python -m pytest -m "unit" -v
```

### Coverage Report

```bash
# Generate coverage report
python -m pytest tests/ --cov=agent --cov-report=html

# View report
open htmlcov/index.html

# Coverage by module
python -m pytest tests/ --cov=agent --cov-report=term-missing

# Specific module coverage
python -m pytest tests/ --cov=agent.cache --cov-report=term
```

---

## Test Markers

**Available markers** (in `conftest.py`):

```python
@pytest.mark.unit           # Unit tests (fast)
@pytest.mark.integration    # Integration tests (medium)
@pytest.mark.slow           # Slow tests (skip by default)
@pytest.mark.requires_api   # Requires API credentials
```

**Usage**:
```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m "integration"

# Run only tests that don't require API
pytest -m "not requires_api"
```

---

## Unit Tests

### LLM Client

**File**: `tests/test_llm_client.py`

**Tests**:
```python
def test_call_with_retry():
    """Test LLM client retry logic"""
    client = LLMClient(provider="dummy")
    response = client.call("Generate 3 slides about Python")
    assert response is not None
    assert len(response) > 0

def test_validation_json_response():
    """Test JSON response validation"""
    client = LLMClient(provider="dummy")
    valid_json = '{"slides": [{"title": "Intro"}]}'
    result = client.validate_json_response(valid_json)
    assert isinstance(result, dict)

def test_retry_exponential_backoff():
    """Test exponential backoff strategy"""
    client = LLMClient(provider="dummy")
    # Mock failing API
    with patch('client.call') as mock_call:
        mock_call.side_effect = Exception("API Error")
        with pytest.raises(Exception):
            client.call_with_retry("prompt", max_retries=3)
```

### Cache System

**File**: `tests/test_cache.py`

**Tests**:
```python
def test_cache_get_set():
    """Test basic cache operations"""
    cache = Cache(cache_dir="workspace/cache")
    cache.set("test_key", "test_value", {})
    assert cache.get("test_key") == "test_value"

def test_cache_content_hash():
    """Test content-based hashing"""
    cache = Cache()
    hash1 = cache._hash_content("Same content")
    hash2 = cache._hash_content("Same content")
    assert hash1 == hash2
    
    hash3 = cache._hash_content("Different content")
    assert hash1 != hash3

def test_cache_expiration():
    """Test cache expiration"""
    cache = Cache(ttl=1)  # 1 second TTL
    cache.set("key", "value", {})
    assert cache.exists("key")
    time.sleep(2)
    assert not cache.exists("key")
```

### Script Generator

**File**: `tests/test_script_generator.py`

**Tests**:
```python
def test_generate_slide_plan():
    """Test slide plan generation"""
    generator = ScriptGenerator(llm_adapter="dummy")
    chapter = Chapter(title="Python", content="Introduction to Python...")
    plan = generator.generate_slide_plan(chapter)
    
    assert len(plan.slides) > 0
    assert all(slide.title for slide in plan.slides)

def test_generate_slides_parallel():
    """Test parallel slide generation"""
    generator = ScriptGenerator(llm_adapter="dummy")
    chapter = Chapter(title="Python", content="...")
    
    slides = generator.generate_slides(chapter, max_workers=2)
    assert len(slides) > 0
    assert all(slide.image_url for slide in slides)
```

### Video Composer

**File**: `tests/test_video_composer.py`

**Tests**:
```python
def test_compose_chapter():
    """Test video composition"""
    composer = VideoComposer()
    script = ChapterScript(
        chapter_id="ch_1",
        slides=[...],  # Mock slides
    )
    
    video_path = composer.compose_chapter(script)
    assert os.path.exists(video_path)
    assert video_path.endswith(".mp4")

@pytest.mark.slow  # Skip by default
def test_compose_with_subtitles():
    """Test subtitle generation and overlay"""
    composer = VideoComposer()
    # Test with actual video file
    subtitles = [
        Subtitle(text="Hello", start=0, end=2),
        Subtitle(text="World", start=2, end=4),
    ]
    video_path = composer.add_subtitles("input.mp4", subtitles)
    assert os.path.exists(video_path)
```

### Google Services Tests

**File**: `tests/test_vertex_adapter.py`

```python
def test_google_services_with_fake_genai():
    """Test GoogleServices with mocked Google API"""
    # Mock google.genai module
    google_services = GoogleServices(llm_model="gemini-test")
    result = google_services.generate_slide_plan("Test content")
    assert isinstance(result, dict)
    assert "slides" in result

@pytest.mark.skipif(not os.getenv("GOOGLE_API_KEY"), reason="Google API key required")
def test_google_services_real_api():
    """Test with real Google API (requires API key)"""
    services = GoogleServices()
    result = services.generate_slide_plan("Generate 2 slides about Python")
    assert result is not None
    assert len(result["slides"]) >= 1
```

---

## Integration Tests

### End-to-End Pipeline

**File**: `tests/test_end_to_end_pipeline.py`

```python
def test_full_pipeline():
    """Test complete pipeline"""
    # Create input
    input_file = "tests/data/sample.md"
    
    # Run pipeline
    result = run_pipeline(
        input_file=input_file,
        provider="dummy",
        output_dir="workspace/test_out",
    )
    
    # Validate output
    assert result.success
    assert os.path.exists("workspace/test_out/videos/chapter_01.mp4")

def test_pipeline_with_cache():
    """Test pipeline with caching"""
    input_file = "tests/data/sample.md"
    
    # First run (no cache)
    start = time.time()
    result1 = run_pipeline(input_file, cache_enabled=True)
    time1 = time.time() - start
    
    # Second run (with cache)
    start = time.time()
    result2 = run_pipeline(input_file, cache_enabled=True)
    time2 = time.time() - start
    
    # Should be significantly faster
    assert time2 < time1 * 0.5  # At least 2x speedup
```

### Resume Functionality

**File**: `tests/test_resume_run.py`

```python
def test_resume_from_checkpoint():
    """Test resuming interrupted pipeline"""
    # Start pipeline
    result = run_pipeline_async("input.md")
    run_id = result.run_id
    
    # Simulate interruption after chapter 2
    # ...
    
    # Resume
    result = run_pipeline(
        "input.md",
        resume_from=run_id,
    )
    
    assert result.success
    assert result.resumed_at_chapter == 3
```

### Google Services TTS Tests

**File**: `tests/test_script_generator.py`, `tests/test_pipeline_image_tts.py`

```python
class MockGoogleServices:
    """Mock Google services for testing."""
    
    def synthesize_speech(self, text: str, out_path=None, voice=None, language=None):
        """Mock TTS - writes text to file."""
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as f:
            f.write(text)
        return out_path

@pytest.mark.skipif(not os.getenv("GOOGLE_API_KEY"), reason="Google API key required")
def test_google_tts_real_api():
    """Test TTS with real Google API"""
    from agent.google import GoogleServices
    services = GoogleServices()
    audio_path = services.synthesize_speech("Test speech", out_path="test.mp3")
    assert os.path.exists(audio_path)
```

---

## System Tests

### CLI Tests

**File**: `tests/test_cli.py`

```python
def test_cli_basic():
    """Test CLI basic functionality"""
    result = subprocess.run([
        "python", "-m", "agent.cli",
        "tests/data/sample.md",
        "--out", "workspace/test_out",
    ])
    assert result.returncode == 0

def test_cli_full_pipeline():
    """Test CLI with full pipeline"""
    result = subprocess.run([
        "python", "-m", "agent.cli",
        "tests/data/sample.md",
        "--full-pipeline",
        "--out", "workspace/test_out",
        "--provider", "dummy",
    ])
    assert result.returncode == 0
    assert os.path.exists("workspace/test_out/videos")

def test_cli_help():
    """Test CLI help"""
    result = subprocess.run([
        "python", "-m", "agent.cli", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--full-pipeline" in result.stdout
```

### Parallel Processing

**File**: `tests/test_parallel_generation.py`

```python
def test_parallel_chapter_processing():
    """Test parallel chapter processing"""
    result = run_pipeline(
        "tests/data/multi_chapter.md",
        max_workers=4,
        provider="dummy",
    )
    assert result.success
    assert result.chapters_processed == 4

def test_parallel_slide_generation():
    """Test parallel slide generation"""
    generator = ScriptGenerator()
    chapter = Chapter(title="Test", content="Long content " * 100)
    
    # Sequential
    slides_seq = generator.generate_slides(chapter, max_workers=1)
    
    # Parallel
    slides_par = generator.generate_slides(chapter, max_workers=4)
    
    # Should produce same results
    assert len(slides_seq) == len(slides_par)
```

---

## Fixtures

**File**: `tests/conftest.py`

Common fixtures for reuse across tests:

```python
@pytest.fixture
def sample_chapter():
    """Sample chapter for testing"""
    return Chapter(
        id="ch_1",
        title="Introduction",
        content="Welcome to the course...",
        order=1,
    )

@pytest.fixture
def sample_script():
    """Sample script for testing"""
    return ChapterScript(
        chapter_id="ch_1",
        slides=[
            Slide(title="Slide 1", content="Content 1"),
            Slide(title="Slide 2", content="Content 2"),
        ],
    )

@pytest.fixture
def temp_workspace(tmp_path):
    """Temporary workspace directory"""
    return tmp_path

@pytest.fixture
def mock_llm_adapter():
    """Mock LLM adapter"""
    adapter = MagicMock()
    adapter.call.return_value = "Mock response"
    return adapter
```

**Usage**:
```python
def test_something(sample_chapter, temp_workspace):
    """Test using fixtures"""
    result = process(sample_chapter, temp_workspace)
    assert result is not None
```

---

## Test Data

### Sample Files

**Location**: `tests/data/`

```
tests/data/
├── sample_lecture.md        # Single chapter
├── multi_chapter.md         # Multiple chapters
├── complex_formatting.md    # Edge cases
└── images/
    ├── sample_image.png
    └── test_slide.jpg
```

**Creating Test Data**:

```python
# tests/conftest.py
def create_sample_markdown():
    """Create sample markdown file"""
    content = """# Chapter 1: Introduction
    
Content here.

## Section 1.1
More content.

# Chapter 2: Main Topic

Content for chapter 2.
"""
    with open("tests/data/sample.md", "w") as f:
        f.write(content)
```

---

## Mocking & Patching

### Mock Adapters

```python
def test_with_mock_adapter():
    """Test with mocked adapter"""
    with patch('agent.adapters.factory.AdapterFactory.create_llm_adapter') as mock:
        mock_adapter = MagicMock()
        mock_adapter.call.return_value = "Mock response"
        mock.return_value = mock_adapter
        
        client = LLMClient()
        response = client.call("prompt")
        assert response == "Mock response"
```

### Mock API Calls

```python
def test_with_mock_api():
    """Mock external API calls"""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"text": "Mock"}]}
        mock_post.return_value = mock_response
        
        adapter = OpenAIAdapter()
        response = adapter.call("prompt")
        assert response == "Mock"
```

### Mock File System

```python
def test_with_mock_filesystem():
    """Mock file system operations"""
    with patch('builtins.open', mock_open(read_data="file content")) as mock_file:
        content = read_file("test.txt")
        assert content == "file content"
        mock_file.assert_called_with("test.txt", "r")
```

---

## Performance Tests

### Benchmarking

```python
def test_script_generation_performance(benchmark):
    """Benchmark script generation"""
    generator = ScriptGenerator(provider="dummy")
    chapter = Chapter(title="Test", content="Content " * 100)
    
    result = benchmark(generator.generate_script, chapter)
    assert result is not None
```

**Run with profiling**:
```bash
pytest tests/test_script_generator.py --profile
```

### Load Testing

```python
def test_high_volume_processing():
    """Test processing many chapters"""
    chapters = [
        Chapter(title=f"Ch {i}", content=f"Content {i}")
        for i in range(100)
    ]
    
    result = run_pipeline_with_chapters(chapters)
    assert result.success
    assert len(result.processed_chapters) == 100
```

---

## Continuous Integration

### GitHub Actions

**File**: `.github/workflows/test.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ --cov=agent --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml
```

### Local Pre-commit Hook

**File**: `.git/hooks/pre-commit`

```bash
#!/bin/bash
echo "Running tests..."
python -m pytest tests/ -m "not slow" --tb=short
if [ $? -ne 0 ]; then
    echo "Tests failed, commit aborted"
    exit 1
fi
```

---

## Test Best Practices

### 1. Arrange-Act-Assert Pattern

```python
def test_script_generator():
    # Arrange
    generator = ScriptGenerator(provider="dummy")
    chapter = Chapter(title="Test", content="...")
    
    # Act
    script = generator.generate_script(chapter)
    
    # Assert
    assert script is not None
    assert len(script.slides) > 0
```

### 2. One Assertion Per Test

```python
# Good
def test_script_has_slides():
    script = generate_script()
    assert len(script.slides) > 0

def test_slides_have_titles():
    script = generate_script()
    assert all(slide.title for slide in script.slides)

# Avoid
def test_script_structure():  # Too many assertions
    script = generate_script()
    assert script is not None
    assert len(script.slides) > 0
    assert all(slide.title for slide in script.slides)
    assert all(slide.image for slide in script.slides)
```

### 3. Use Descriptive Names

```python
# Good
def test_script_generator_creates_required_number_of_slides():
    pass

def test_cache_returns_none_for_expired_entries():
    pass

# Avoid
def test_it_works():
    pass

def test_cache_test():
    pass
```

### 4. Keep Tests Independent

```python
# Good
def test_cache_get():
    cache = Cache()  # New instance
    cache.set("key", "value", {})
    assert cache.get("key") == "value"

# Avoid - tests shouldn't depend on order
def test_cache():
    global cache_instance
    cache_instance.set("key", "value", {})
    
def test_cache_get():
    assert cache_instance.get("key") == "value"  # Depends on previous test
```

### 5. Use Parametrized Tests

```python
@pytest.mark.parametrize("provider,expected_type", [
    ("openai", OpenAIAdapter),
    ("vertex", VertexAdapter),
    ("dummy", DummyAdapter),
])
def test_adapter_factory(provider, expected_type):
    adapter = AdapterFactory.create_llm_adapter(provider)
    assert isinstance(adapter, expected_type)
```

---

## Coverage Goals

### Target Coverage

| Component | Target | Current |
|-----------|--------|---------|
| `agent/llm_client.py` | 100% | 100% ✅ |
| `agent/cache.py` | 95% | 97% ✅ |
| `agent/script_generator.py` | 90% | 92% ✅ |
| `agent/video_composer.py` | 85% | 88% ✅ |
| `agent/google/` | 80% | 85% ✅ |
| **Overall** | **85%** | **~95%** ✅ |

### Improving Coverage

```bash
# Find uncovered lines
pytest tests/ --cov=agent --cov-report=term-missing

# Focus on low-coverage modules
pytest tests/test_video_composer.py --cov=agent.video_composer --cov-report=term-missing
```

---

## Troubleshooting Tests

### Issue: Test fails locally but passes in CI

**Causes**: Environment differences, missing dependencies, timing issues

**Solutions**:
```bash
# Run with exact same environment as CI
docker run --rm -v $(pwd):/app python:3.9 bash -c "cd /app && pytest tests/"

# Run with verbose output
pytest tests/ -vv -s

# Run with print debugging
pytest tests/ -s
```

### Issue: Flaky tests (intermittent failures)

**Causes**: Timing issues, external dependencies, race conditions

**Solutions**:
```python
# Add explicit waits
time.sleep(0.1)  # If testing async code

# Mock time-dependent functions
@patch('time.time')
def test_with_mocked_time(mock_time):
    mock_time.return_value = 1000
    ...

# Mark as flaky (don't fail CI)
@pytest.mark.flaky(reruns=3)
def test_something():
    ...
```

### Issue: Out of memory

**Solutions**:
```bash
# Run tests serially
pytest tests/ -n 1

# Run with limited processes
pytest tests/ -n 4

# Skip slow/memory-heavy tests
pytest -m "not slow"
```

---

## Test Checklist

- [ ] All new features have tests
- [ ] Coverage > 85%
- [ ] All tests pass locally before pushing
- [ ] CI tests pass
- [ ] No test warnings/deprecations
- [ ] Mock external API calls
- [ ] Test both success and failure paths
- [ ] Use descriptive test names
- [ ] Fixture names clearly indicate purpose
- [ ] Documentation updated for new tests

---

**For additional help**: See [README.md](../README.md) or specific component tests.
