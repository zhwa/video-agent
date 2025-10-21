import os
from typing import Any, Dict, cast

from agent.io import list_documents, read_markdown


def test_list_documents(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.md").write_text("# Hello")
    (d / "b.pdf").write_text("PDFDATA")
    (d / "hidden.txt").write_text("nope")
    nested = d / "sub"
    nested.mkdir()
    (nested / "c.markdown").write_text("# nested")

    results = list_documents(d)
    assert any(str(p).endswith("a.md") for p in results)
    assert any(str(p).endswith("b.pdf") for p in results)
    assert any(str(p).endswith("c.markdown") for p in results)


def test_read_markdown_front_matter(tmp_path):
    f = tmp_path / "sample.md"
    f.write_text("""---\ntitle: My Doc\n---\n# Header\nContent here""")
    data = read_markdown(f)
    metadata = cast(Dict[str, Any], data.get("metadata", {}))
    assert metadata.get("title") == "My Doc"
    assert "Header" in data.get("text", "")
