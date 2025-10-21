from agent.script_generator import generate_slides_for_chapter
from agent.adapters.llm import DummyLLMAdapter


def test_generate_slides_basic():
    chapter = {"id": "c01", "title": "Intro", "text": "This is sentence one. This is sentence two. This is sentence three. This is sentence four."}
    adapter = DummyLLMAdapter()
    result = generate_slides_for_chapter(chapter, adapter, max_slides=2)
    assert result["chapter_id"] == "c01"
    slides = result["slides"]
    assert isinstance(slides, list)
    assert len(slides) >= 1
    assert "title" in slides[0]