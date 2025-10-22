# Video Agent

A professional-grade pipeline that converts lecture content (PDF/Markdown) into structured video lectures with AI-generated slides, synthesized audio, and automatic video composition.

##  Quick Start

```bash
git clone https://github.com/zhwa/video-agent.git
cd video-agent
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out
```

##  Documentation

- **[Chapter 1: Architecture Overview](docs/01_architecture_overview.md)** - System design and data flow
- **[Chapter 2: Quick Start](docs/02_quick_start.md)** - Installation and basic usage
- **[Chapter 3: Component Guide](docs/03_component_guide.md)** - Detailed component breakdown
- **[Chapter 4: Deployment](docs/04_deployment.md)** - Production deployment guide
- **[Chapter 5: Testing](docs/05_testing.md)** - Testing strategies and test suite

##  Key Features

- Multi-provider support (OpenAI, Vertex AI, ElevenLabs, etc.)
- Intelligent caching with 60%+ speedup
- Checkpoint/resume for interrupted runs
- Parallel processing support
- 88 comprehensive tests

##  Testing

```bash
python -m pytest tests/ -v
```

---

**For detailed information, see the documentation chapters above.**
