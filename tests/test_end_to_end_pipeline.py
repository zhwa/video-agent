import os
from agent.langgraph_nodes import build_graph_description, run_graph_description
from agent.adapters.llm import DummyLLMAdapter
from pathlib import Path


def test_end_to_end_markdown_pipeline(tmp_path, monkeypatch):
    # Create a simple markdown file
    md = tmp_path / "sample.md"
    md.write_text("# Chapter 1\n\nThis is one. This is two. This is three.", encoding="utf-8")

    # Configure dummy providers
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))

    desc = build_graph_description(str(md))
    # Use DummyLLMAdapter to avoid remote calls
    adapter = DummyLLMAdapter()
    result = run_graph_description(desc, llm_adapter=adapter)

    # Validate structure
    assert "segment" in result
    assert "script_gen" in result
    for ch_res in result["script_gen"]:
        assert "chapter_id" in ch_res
        for slide in ch_res.get("slides", []):
            assert "audio_url" in slide
            assert slide["audio_url"].startswith("file://")
            assert "image_url" in slide
            assert slide["image_url"].startswith("file://")