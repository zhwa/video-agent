import time
import threading
from agent.langgraph_nodes import run_graph_description, build_graph_description
from agent.adapters.llm import LLMAdapter


class SlowDummyAdapter(LLMAdapter):
    def __init__(self, sleep_time=0.2, concurrency_counter=None):
        self.sleep_time = sleep_time
        self.counter = concurrency_counter or {"val": 0, "max": 0, "lock": threading.Lock()}

    def generate_from_prompt(self, prompt: str):
        # unused for this test
        return {}

    def generate_slide_plan(self, chapter_text: str, max_slides=None, run_id=None, chapter_id=None):
        # simulate work and track concurrency
        with self.counter["lock"]:
            self.counter["val"] += 1
            if self.counter["val"] > self.counter["max"]:
                self.counter["max"] = self.counter["val"]
        time.sleep(self.sleep_time)
        with self.counter["lock"]:
            self.counter["val"] -= 1
        return {"slides": [{"id": "s01", "title": "T", "bullets": ["x"], "visual_prompt": "v", "estimated_duration_sec": 30, "speaker_notes": "n"}]}


def test_parallel_generation_respects_max_workers(monkeypatch):
    # Build a fake document with 6 small chapters
    chapters = []
    for i in range(6):
        chapters.append({"id": f"chapter-{i+1:02d}", "title": f"C{i+1}", "text": "One. Two."})

    desc = {"nodes": [{"id": "ingest", "type": "ingest", "config": {"path": "dummy"}}, {"id": "segment", "type": "segment", "config": {}}, {"id": "script_gen", "type": "script_generator", "config": {"adapter": "dummy"}}], "edges": [("ingest", "segment"), ("segment", "script_gen")]}  # noqa: E501

    # Monkeypatch segmenter outputs by monkeypatching read_file and segmentation functions
    def fake_read_file(path):
        return {"type": "markdown", "text": "dummy"}

    def fake_segment_text_into_chapters(text):
        return chapters

    from agent import io as io_mod
    from agent import segmenter as seg_mod

    monkeypatch.setattr(io_mod, "read_file", fake_read_file)
    monkeypatch.setattr(seg_mod, "segment_text_into_chapters", lambda t: chapters)

    counter = {"val": 0, "max": 0, "lock": threading.Lock()}
    adapter = SlowDummyAdapter(sleep_time=0.2, concurrency_counter=counter)

    # Configure env to use 3 workers
    import os

    os.environ["MAX_WORKERS"] = "3"
    # Run
    result = run_graph_description(desc, llm_adapter=adapter)
    # Assert concurrency observed <= 3
    assert counter["max"] <= 3
    # Also verify we produced script_gen results for all chapters
    assert len(result["script_gen"]) == len(chapters)
