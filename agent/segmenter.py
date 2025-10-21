from typing import List, Dict, Any
import re


def _simple_toc_detector(text: str) -> List[Dict[str, Any]]:
    """A very small heuristic TOC detector.

    Looks for lines that look like "Chapter 1: Title ........ 12" or
    H1/H2 formatted title lines near the beginning.

    Returns list of {"title":..., "page_hint": int|None}
    """
    lines = text.splitlines()
    toc_entries = []
    for line in lines[:200]:
        m = re.match(r"^(Chapter\s+\d+[:\.]?\s*(.+?))\s+\.{2,}\s*(\d+)$", line)
        if m:
            title = m.group(2).strip()
            page = int(m.group(3))
            toc_entries.append({"title": title, "page_hint": page})
    return toc_entries


def segment_text_into_chapters(text: str, max_chars_per_chapter: int = 3000) -> List[Dict[str, Any]]:
    """Split a long text into chapters.

    Strategy:
    1. Try TOC detection; if found, split by page hints when available.
    2. Else: split by H1/H2 markdown-style headers (#, ##) or common 'Chapter' headings.
    3. Else: naive sliding split by sentences trying to keep chapters <= max_chars.

    Returns list of chapters: {"id":..., "title":..., "text":...}
    """
    # Normalize newlines
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    toc = _simple_toc_detector(normalized)
    chapters = []
    if toc:
        # TODO: proper mapping from page_hint to offsets requires page-level info.
        # For now just create chapter stubs from TOC with empty text placeholder.
        for i, e in enumerate(toc, start=1):
            chapters.append({"id": f"chapter-{i:02d}", "title": e.get("title") or f"Chapter {i}", "text": ""})
        return chapters

    # Try markdown headers
    hdrs = list(re.finditer(r"^#{1,3}\s+(.+)$", normalized, flags=re.MULTILINE))
    if hdrs:
        for i, m in enumerate(hdrs):
            start = m.end()
            end = hdrs[i + 1].start() if i + 1 < len(hdrs) else len(normalized)
            title = m.group(1).strip()
            body = normalized[start:end].strip()
            chapters.append({"id": f"chapter-{i+1:02d}", "title": title, "text": body})
        return chapters

    # Try "Chapter" headings
    chap_heads = list(re.finditer(r"^Chapter\s+\d+[:\.]?\s*(.*)$", normalized, flags=re.MULTILINE | re.IGNORECASE))
    if chap_heads:
        for i, m in enumerate(chap_heads):
            start = m.end()
            end = chap_heads[i + 1].start() if i + 1 < len(chap_heads) else len(normalized)
            title = m.group(1).strip() or m.group(0).strip()
            body = normalized[start:end].strip()
            chapters.append({"id": f"chapter-{i+1:02d}", "title": title, "text": body})
        return chapters

    # Fallback: chunk by approximate size at sentence boundary
    try:
        from nltk.tokenize import sent_tokenize
        try:
            sentences = sent_tokenize(normalized)
        except LookupError:
            # NLTK data (punkt) not installed; fall back to naive splitter
            sentences = [s.strip() for s in re.split(r"(?<=[\.\?\!])\s+", normalized) if s.strip()]
    except Exception:
        # naive split on sentence-end characters
        sentences = [s.strip() for s in re.split(r"(?<=[\.\?\!])\s+", normalized) if s.strip()]

    # If the sentence splitter produced a single long "sentence" (e.g.
    # when the document has no punctuation), split by words to produce
    # reasonable chunks.
    if len(sentences) == 1 and len(sentences[0]) > max_chars_per_chapter:
        words = sentences[0].split()
        cur = []
        cur_len = 0
        chap_no = 1
        for w in words:
            cur.append(w)
            cur_len += len(w) + 1
            if cur_len >= max_chars_per_chapter:
                chapters.append({
                    "id": f"chapter-{chap_no:02d}",
                    "title": f"Chapter {chap_no}",
                    "text": " ".join(cur),
                })
                chap_no += 1
                cur = []
                cur_len = 0
        if cur:
            chapters.append({
                "id": f"chapter-{chap_no:02d}",
                "title": f"Chapter {chap_no}",
                "text": " ".join(cur),
            })
        return chapters

    cur = []
    cur_len = 0
    chap_no = 1
    for s in sentences:
        cur.append(s)
        cur_len += len(s) + 1
        if cur_len >= max_chars_per_chapter:
            chapters.append({"id": f"chapter-{chap_no:02d}", "title": f"Chapter {chap_no}", "text": "\n\n".join(cur)})
            chap_no += 1
            cur = []
            cur_len = 0
    if cur:
        chapters.append({"id": f"chapter-{chap_no:02d}", "title": f"Chapter {chap_no}", "text": "\n\n".join(cur)})
    return chapters


def segment_pages_into_chapters(pages: List[Dict[str, Any]], max_chars_per_chapter: int = 3000) -> List[Dict[str, Any]]:
    """Segment PDF pages into chapters by using the per-page text and a
    fallback algorithm that concatenates pages until a chapter boundary is likely.

    pages: list of {'page_number':int, 'text':str}
    Returns chapters as in segment_text_into_chapters but with page_range.
    """
    all_text = "\n\n".join(p.get("text", "") for p in pages)
    possible = segment_text_into_chapters(all_text, max_chars_per_chapter=max_chars_per_chapter)
    # best-effort mapping from character offsets back to pages
    # Build an offset index of pages
    offsets = []
    cur = 0
    for p in pages:
        t = p.get("text", "")
        offsets.append((cur, cur + len(t), p.get("page_number")))
        cur += len(t) + 2  # account for separator

    def find_page_for_offset(off: int) -> int:
        for a, b, pg in offsets:
            if a <= off <= b:
                return pg
        return offsets[-1][2] if offsets else 1

    chapters = []
    pos = 0
    for i, chap in enumerate(possible):
        text = chap.get("text", "")
        start_off = pos
        end_off = pos + len(text)
        start_page = find_page_for_offset(start_off)
        end_page = find_page_for_offset(end_off)
        chapters.append({
            "id": chap.get("id"),
            "title": chap.get("title"),
            "text": text,
            "page_range": [start_page, end_page],
        })
        pos = end_off + 2
    return chapters
