"""Agent package - video composition and orchestration.

This package contains the GraphFlow-based video composition engine with support
for parallel chapter processing, checkpointing, and various adapter integrations.
"""

__version__ = "0.2.0"

from .io import read_markdown, read_pdf, read_file, list_documents
from .segmenter import (
    segment_text_into_chapters,
    segment_pages_into_chapters,
)
from .adapters.llm import LLMAdapter, DummyLLMAdapter

__all__ = [
    "read_markdown",
    "read_pdf",
    "read_file",
    "list_documents",
    "segment_text_into_chapters",
    "segment_pages_into_chapters",
]
