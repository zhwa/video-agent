import os
import pytest
import time
import threading
from agent.graphflow_nodes import run_graph_description, build_graph_description


class SlowMockGoogleServices:
    """Mock Google services that simulates slow LLM calls for concurrency testing."""
    def __init__(self, sleep_time=0.2, concurrency_counter=None):
        self.sleep_time = sleep_time
        self.counter = concurrency_counter or {"val": 0, "max": 0, "lock": threading.Lock()}

    def generate_text(self, prompt: str):
        # unused for this test
        return "{}"

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


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_GENAI_API_KEY"),
    reason="Google API key required for integration test"
)
def test_parallel_generation_respects_max_workers(monkeypatch):
    # Build a fake document with 6 small chapters
    chapters = []
    for i in range(6):
        chapters.append({
            "id": f"chapter-{i+1:02d}",
            "title": f"C{i+1}",
            "text": "One. Two."
        })

    # Monkeypatch graphflow_nodes (which is used by run_graph_description)
    def fake_read_file(path):
        return {"type": "markdown", "text": "dummy"}

    import agent.graphflow_nodes as gn_mod
    monkeypatch.setattr(gn_mod, "read_file", fake_read_file)
    monkeypatch.setattr(gn_mod, "segment_text_into_chapters", lambda t: chapters)

    desc = build_graph_description("dummy")

    counter = {"val": 0, "max": 0, "lock": threading.Lock()}
    google = SlowMockGoogleServices(sleep_time=0.2, concurrency_counter=counter)

    # Configure env to use 3 workers
    import os
    os.environ["MAX_WORKERS"] = "3"
    
    # Run
    result = run_graph_description(desc, llm_adapter=google)
    
    # Assert concurrency observed <= 3
    assert counter["max"] <= 3
    # Also verify we produced script_gen results for all chapters
    assert len(result["script_gen"]) == len(chapters)

