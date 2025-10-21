from agent.segmenter import segment_text_into_chapters


def test_segment_by_chapter_headings():
    text = "Chapter 1: Intro\nThis is intro.\nChapter 2: Methods\nThis is methods."
    chapters = segment_text_into_chapters(text)
    assert len(chapters) == 2
    assert "Intro" in chapters[0]["title"]
    assert "Methods" in chapters[1]["title"]


def test_segment_markdown_headers():
    md = "# Title\nIntro text\n## Section 1\nBody1\n## Section 2\nBody2"
    ch = segment_text_into_chapters(md)
    # We expect segmentation at markdown headers (two sections)
    assert any("Section 1" in c.get("title", "") for c in ch)
    assert any("Section 2" in c.get("title", "") for c in ch)


def test_segment_fallback_chunks():
    # Generate long text with no headings
    long_text = " ".join(["word"] * 1000)
    chapters = segment_text_into_chapters(long_text, max_chars_per_chapter=200)
    assert len(chapters) >= 2
    total_len = sum(len(c.get("text", "")) for c in chapters)
    assert total_len > 0
