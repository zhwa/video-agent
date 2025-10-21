# Video Agent

A demo pipeline that converts lecture content (PDF/Markdown) into structured slides, synthesized audio, and final video lectures.

---

## Quick Start

**Convert a Markdown/PDF file to video**:

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run with dummy providers (no API keys needed)
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out

# Or with real providers (OpenAI, Vertex, etc.)
python -m agent.cli lesson.md --full-pipeline --out workspace/out --provider openai
```

---

## Documentation

**Start here**:

- **Learning**: `docs/chapter1_overview.md`  Foundations and architecture
- **Configuration**: `docs/chapter2b_configuration.md`  Environment variables and setup
- **Development**: `docs/chapter4_code_walkthrough.md`  Code structure
- **Performance**: `docs/appendix_a_caching.md`  Caching and optimization
- **Testing**: `docs/chapter8_testing_strategies.md`  Test patterns
- **Exercises**: `docs/chapter9_getting_started.md`  5 hands-on exercises

**Full structure**: 11 comprehensive chapters + appendix covering architecture, design patterns, error handling, concurrency, testing, and optimization.

---

**Key features**:
- Thread-safe file locking with timeout and atomic writes
- Retry with exponential backoff and LLM output validation
- Adapter factory with graceful fallback to dummy providers
- Resume support for interrupted runs
- Content-based caching (60%+ speedup with 80% hit rate)

---

## Documentation Quality:  Enhanced

Topics covered: Overview, architecture, configuration, design concepts, code walkthrough, design patterns, error handling, concurrency, testing, exercises, and performance optimization.

---

## Testing

```powershell
# Run all tests
python -m pytest -q

# Run specific test
python -m pytest tests/test_script_generator.py -v

# With coverage
python -m pytest --cov=agent tests/
```

---

## Project Quality

| Category | Metric | Status |
|----------|--------|--------|
| Tests | 76/76 passing |  |
| Code | ~4,500 LOC (core) |  |
| Docs | 11 chapters, 3,700+ lines |  |
| Architecture | Clean, modular |  |
| Error Handling | Comprehensive |  |
| Thread Safety | Proper locking |  |
| Production Ready | Yes |  |

---

## Project Structure

```
agent/                # Core pipeline
 cli.py               # Entry point
 langgraph_nodes.py   # Pipeline execution
 script_generator.py  # Slide generation
 video_composer.py    # Video assembly
 cache.py             # Content-based caching
 runs_safe.py         # Thread-safe checkpointing
 adapters/            # Pluggable providers

docs/                 # Comprehensive textbook
 chapter1_overview.md
 chapter2_architecture.md
 chapter2b_configuration.md
 chapter3_key_concepts.md
 ... (chapters 4-9, appendix_a)

tests/                   # 25+ test files
examples/                # Sample content
```

---