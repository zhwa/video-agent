# Video Lecture Agent

A LangGraph-based agent that converts PDF and Markdown documents into structured video lecture scripts with AI-generated content.

## Project Status

- ✅ **Milestone 1**: Ingest + Segmentation PoC - COMPLETE
- ✅ **Milestone 2**: Script Generation PoC - COMPLETE  
- 🔄 **Milestone 3**: TTS + Visual Generation - IN PROGRESS
- ⏳ **Milestone 4+**: Video Composition, Persistence, Production - PLANNED

See [`docs/langgraph_agent_plan.md`](docs/langgraph_agent_plan.md) for the complete plan and [`docs/milestone_2_completion.md`](docs/milestone_2_completion.md) for the latest completion report.

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: Install PDF support
pip install PyMuPDF pdfplumber

# Optional: Install LLM providers
pip install openai google-cloud-aiplatform google-generativeai
```

### Basic Usage

```bash
# Process a markdown file
python -m agent.cli examples/sample_lecture.md

# Process with custom output directory
python -m agent.cli my_document.pdf --out results/

# Enable LLM logging for debugging
python -m agent.cli document.md --llm-out logs/

# Use specific LLM provider
python -m agent.cli document.md --provider openai

# Enable parallel processing
python -m agent.cli document.md --max-workers 4 --llm-rate 2.0
```

### Configuration

Set environment variables for LLM providers:

```bash
# OpenAI
export OPENAI_API_KEY="your-key-here"
export OPENAI_MODEL="gpt-4o-mini"

# Google Vertex AI
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
export VERTEX_MODEL="text-bison"
export GCP_PROJECT="your-project-id"

# Or use Google Generative AI
export GOOGLE_API_KEY="your-api-key"

# General settings
export LLM_PROVIDER="vertex"  # or "openai"
export LLM_MAX_RETRIES=3
export MAX_WORKERS=4
export LLM_RATE_LIMIT=2.0
```

## Features

### Current Features (Milestones 1-2)

- 📄 **Document Ingestion**: PDF and Markdown support
- 📚 **Smart Segmentation**: Automatic chapter detection using headers, TOC, or heuristics
- 🤖 **AI Script Generation**: Generate structured slide plans using LLMs
- 🔄 **Retry & Validation**: Automatic retry with repair for invalid LLM responses
- 📝 **Schema Validation**: Ensures all slides meet required structure
- ⚡ **Parallel Processing**: Concurrent chapter processing with rate limiting
- 📊 **Comprehensive Logging**: Track all LLM prompts, responses, and validation
- 🔌 **Provider Flexibility**: Easy switching between Vertex AI, OpenAI, or deterministic mode

### Planned Features (Milestones 3+)

- 🎤 Text-to-Speech synthesis
- 🎨 Visual generation from prompts
- 🎬 Video composition
- 💾 Artifact storage (GCS, MinIO, S3)
- 🔍 Vector DB integration for retrieval
- 👤 Human-in-the-loop review
- 💰 Cost tracking and quotas

## Architecture

```
┌─────────────────┐
│  Input Files    │ PDF, Markdown, Directory
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Ingestion     │ Read files, extract text
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Segmentation   │ Split into chapters
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Script Generator│ Generate slide plans (LLM)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Adapters   │ Vertex AI / OpenAI / Dummy
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validation     │ Schema checking & repair
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Output JSON    │ Structured results
└─────────────────┘
```

## Output Format

The agent produces a JSON file containing:

```json
{
  "ingest": {
    "type": "markdown",
    "text": "...",
    "metadata": { "title": "..." }
  },
  "segment": [
    {
      "id": "chapter-01",
      "title": "Introduction",
      "text": "..."
    }
  ],
  "script_gen": [
    {
      "chapter_id": "chapter-01",
      "slides": [
        {
          "slide_id": "s01",
          "title": "Overview",
          "bullets": ["Point 1", "Point 2"],
          "visual_prompt": "An illustration showing...",
          "estimated_duration_sec": 60,
          "speaker_notes": "Detailed script..."
        }
      ]
    }
  ]
}
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_script_generator.py -v

# Run with coverage
pytest tests/ --cov=agent --cov-report=html
```

### Project Structure

```
video-agent/
├── agent/                      # Main package
│   ├── adapters/              # LLM, TTS, Image adapters
│   │   ├── llm.py            # LLM adapter interfaces
│   │   ├── openai_adapter.py # OpenAI implementation
│   │   ├── google_vertex_adapter.py # Vertex AI implementation
│   │   ├── schema.py         # JSON schema validation
│   │   └── factory.py        # Adapter factory
│   ├── storage/              # Storage adapters
│   ├── cli.py                # Command-line interface
│   ├── io.py                 # Document ingestion
│   ├── segmenter.py          # Chapter segmentation
│   ├── script_generator.py   # Slide plan generation
│   ├── llm_client.py         # LLM client with retry logic
│   ├── prompts.py            # Prompt building
│   ├── parallel.py           # Concurrent processing
│   └── langgraph_nodes.py    # LangGraph workflow
├── config/
│   └── providers.example.yaml # Provider configuration
├── templates/
│   └── slide_prompt.txt      # Slide generation prompt
├── tests/                     # Test suite
├── examples/                  # Example documents
└── docs/                      # Documentation
```

### Adding a New LLM Provider

1. Create a new adapter class in `agent/adapters/`:

```python
from .llm import LLMAdapter

class MyProviderAdapter(LLMAdapter):
    def generate_from_prompt(self, prompt: str) -> Any:
        # Call your provider's API
        response = my_provider.generate(prompt)
        return response
```

2. Update `agent/adapters/factory.py`:

```python
def get_llm_adapter(provider: Optional[str] = None) -> LLMAdapter:
    if chosen == "myprovider":
        try:
            from .myprovider_adapter import MyProviderAdapter
            return MyProviderAdapter()
        except Exception:
            return DummyLLMAdapter()
```

3. Add tests in `tests/test_myprovider_adapter.py`

## Contributing

This is an internal project following the development plan in [`docs/langgraph_agent_plan.md`](docs/langgraph_agent_plan.md).

Current focus: **Milestone 3** - TTS pipeline and visual generation.

## License

Internal use only.

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Google Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Project Plan](docs/langgraph_agent_plan.md)
- [Milestone TODO](docs/milestone_todo.md)
- [Milestone 2 Completion Report](docs/milestone_2_completion.md)
