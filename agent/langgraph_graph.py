import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from .io import read_file, list_documents, read_pdf, read_markdown
from .segmenter import segment_pages_into_chapters, segment_text_into_chapters


class LectureAgentRunner:
    """A lightweight runner for Milestone 1.

    This class provides a simple entry point that will later be wired into a
    LangGraph workflow. For now it runs ingestion and segmentation sequentially
    so it is easy to test.
    """

    def __init__(self, workspace_dir: Optional[str] = None):
        base = Path(workspace_dir) if workspace_dir else Path.cwd() / "workspace"
        self.workspace = Path(base)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def ingest_and_segment(self, path: str) -> Dict[str, Any]:
        """If path is a directory, scan it and run ingest+segment for each file.

        Returns a dict with filenames as keys and chapter lists as values.
        """
        p = Path(path)
        results: Dict[str, Any] = {}
        if p.is_dir():
            files = list_documents(p)
            for f in files:
                results[f] = self._process_file(f)
        else:
            results[str(p)] = self._process_file(str(p))
        return results

    def _process_file(self, file_path: str) -> List[Dict[str, Any]]:
        info = read_file(file_path)
        if info.get("type") == "pdf":
            pages = info.get("pages", [])
            chapters = segment_pages_into_chapters(pages)
            return chapters
        if info.get("type") == "markdown":
            text = info.get("text", "")
            chapters = segment_text_into_chapters(text)
            return chapters
        raise ValueError(f"Unsupported file type for {file_path}")

    def save_chapters_json(self, file_path: str, chapters: List[Dict[str, Any]]) -> str:
        import json

        out = self.workspace / (Path(file_path).stem + "_chapters.json")
        out.write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out)
