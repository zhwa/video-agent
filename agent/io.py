import os
import re
from pathlib import Path
from typing import Any, Dict, List, Union, Optional, cast

import yaml


def list_documents(directory: Union[str, Path], extensions: Optional[List[str]] = None) -> List[str]:
    """Recursively list PDF and Markdown files in a directory.

    Returns a sorted list of absolute file paths.
    """
    if extensions is None:
        extensions = [
            ".pdf",
            ".md",
            ".markdown",
        ]
    p = Path(directory)
    if not p.exists():
        return []
    results = []
    for root, dirs, files in os.walk(p):
        # skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if fn.startswith("."):
                continue
            if any(fn.lower().endswith(ext) for ext in extensions):
                results.append(str(Path(root) / fn))
    results.sort()
    return results


def read_markdown(file_path: Union[str, Path]) -> Dict[str, Union[str, Dict]]:
    """Load markdown file and extract optional YAML front-matter.

    Returns a dict: { 'type': 'markdown', 'text': ..., 'metadata': {...} }
    """
    p = Path(file_path)
    text = p.read_text(encoding="utf-8")

    # YAML front matter (---\n...\n---\n)
    fm_match = re.match(r"\A\s*---\s*\n(.*?)\n---\s*\n(.*)\Z", text, flags=re.DOTALL)
    metadata: Dict[str, Any] = {}
    if fm_match:
        raw_meta = fm_match.group(1)
        body = fm_match.group(2)
        try:
            # safe_load returns Any; cast to a dict for downstream usage
            metadata = cast(Dict[str, Any], yaml.safe_load(raw_meta) or {})
        except Exception:
            metadata = {"_front_matter_parse_error": True}
        text_body = body
    else:
        text_body = text

    # Derive a title if not present
    if "title" not in metadata:
        # try first markdown H1
        m = re.search(r"^#\s+(.+)$", text_body, flags=re.MULTILINE)
        if m:
            metadata["title"] = m.group(1).strip()
        else:
            metadata["title"] = p.stem

    return {"type": "markdown", "text": text_body, "metadata": metadata}


def read_pdf(file_path: Union[str, Path]) -> Dict:
    """Read PDF file into page-oriented structure.

    Tries PyMuPDF (fitz) first, then pdfplumber as a fallback. If neither library
    is installed an ImportError is raised.

    Returns: { 'type': 'pdf', 'pages':[{'page_number':int,'text':str}], 'metadata': {...} }
    """
    p = Path(file_path)
    # Try PyMuPDF (fitz)
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(p))
        pages = []
        for i in range(len(doc)):
            page = doc.load_page(i)
            text = page.get_text("text") or ""
            pages.append({"page_number": i + 1, "text": text})
        metadata = {k: v for k, v in getattr(doc, "metadata", {}).items() if v}
        doc.close()
        return {"type": "pdf", "pages": pages, "metadata": metadata}
    except Exception:
        # Fall back to pdfplumber
        try:
            import pdfplumber

            pages = []
            with pdfplumber.open(str(p)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append({"page_number": i + 1, "text": text})
                metadata = getattr(pdf, "metadata", {}) or {}
            return {"type": "pdf", "pages": pages, "metadata": metadata}
        except Exception:
            raise ImportError(
                "No PDF backend available. Install PyMuPDF (fitz) or pdfplumber to read PDFs."
            )


def read_file(path: Union[str, Path]) -> Dict:
    """Dispatch to the appropriate reader based on extension.

    Supported types: .md/.markdown -> read_markdown, .pdf -> read_pdf
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    suffix = p.suffix.lower()
    if suffix in (".md", ".markdown"):
        return read_markdown(p)
    if suffix == ".pdf":
        return read_pdf(p)
    raise ValueError(f"Unsupported file type: {suffix}")
