from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, List, Any, Optional


class SimpleRateLimiter:
    """Simple blocking rate limiter that ensures at most `rate` calls per second.

    This uses a tiny critical section to space out calls. It's simple and
    adequate for moderate concurrency; it is not a high-performance token
    bucket implementation.
    """

    def __init__(self, rate: float):
        assert rate > 0
        self._interval = 1.0 / rate
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last = time.time()


def run_tasks_in_threads(tasks: Iterable[Callable[[], Any]], max_workers: int = 4, rate_limit: Optional[float] = None) -> List[Any]:
    """Run callables concurrently and return results in submission order.

    tasks: iterable of zero-arg callables. This helper will submit them to a
    ThreadPoolExecutor and optionally apply a rate-limit before invoking each
    callable.
    """
    rate_limiter = SimpleRateLimiter(rate_limit) if rate_limit else None
    results = []
    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for task in tasks:
            if rate_limiter:
                # wrap the task to wait on the limiter before calling
                def make_task(t):
                    def _inner():
                        rate_limiter.wait()
                        return t()

                    return _inner

                wrapped = make_task(task)
                futures.append(ex.submit(wrapped))
            else:
                futures.append(ex.submit(task))
        # gather results in submission order
        for f in futures:
            results.append(f.result())
    return results
