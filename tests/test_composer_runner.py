import threading
import time
from agent.composer_runner import compose_chapters_parallel


class SlowFakeComposer:
    def __init__(self, counter, sleep=0.2):
        self.counter = counter
        self.sleep = sleep

    def compose_and_upload_chapter_video(self, slides, run_id, chapter_id):
        with self.counter["lock"]:
            self.counter["val"] += 1
            if self.counter["val"] > self.counter["max"]:
                self.counter["max"] = self.counter["val"]
        time.sleep(self.sleep)
        with self.counter["lock"]:
            self.counter["val"] -= 1
        return {"video_url": f"file://{chapter_id}.mp4"}


def test_compose_chapters_parallel_respects_limit():
    counter = {"val": 0, "max": 0, "lock": threading.Lock()}
    comp = SlowFakeComposer(counter)
    chapters = [{"chapter_id": f"c{i:02d}", "slides": []} for i in range(6)]
    res = compose_chapters_parallel(comp, chapters, run_id="runx", max_workers=3)
    assert counter["max"] <= 3
    assert len(res) == len(chapters)
