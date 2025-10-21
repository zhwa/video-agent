from __future__ import annotations

import time
import threading
from typing import Dict, Any


class Telemetry:
    """A tiny in-memory telemetry collector for tests and debugging.

    This is intentionally minimal: it tracks timings and counters in process memory.
    For production, replace with a proper metrics backend.
    """

    def __init__(self):
        self._timings: Dict[str, list[float]] = {}
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()

    def record_timing(self, name: str, seconds: float) -> None:
        with self._lock:
            self._timings.setdefault(name, []).append(seconds)

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def get_timings(self) -> Dict[str, list[float]]:
        return dict(self._timings)

    def get_counters(self) -> Dict[str, int]:
        return dict(self._counters)


# A module-level default collector that other modules can import and use.
_default = Telemetry()


def get_collector() -> Telemetry:
    return _default


def record_timing(name: str, seconds: float) -> None:
    _default.record_timing(name, seconds)


def increment(name: str, amount: int = 1) -> None:
    _default.increment(name, amount)
