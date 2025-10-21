"""Agent package - ingestion and segmentation utilities.

This package contains lightweight, testable helpers for Milestone 1 (ingest +
chapter segmentation). Modules are intentionally small and free of heavy
side-effects so tests can run on machines without all optional dependencies.
"""

__version__ = "0.1.0"

from .io import read_markdown, read_pdf, read_file, list_documents
from .segmenter import (
    segment_text_into_chapters,
    segment_pages_into_chapters,
)
from .langgraph_graph import LectureAgentRunner
from .adapters.llm import LLMAdapter, DummyLLMAdapter

__all__ = [
    "read_markdown",
    "read_pdf",
    "read_file",
    "list_documents",
    "segment_text_into_chapters",
    "segment_pages_into_chapters",
]
