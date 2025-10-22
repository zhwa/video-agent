"""Unified monitoring module for logging and telemetry.

This module consolidates logging configuration and in-memory metrics collection
for the Video Agent. It provides centralized access to both structured logging
and lightweight telemetry tracking.
"""

import logging
import sys
import threading
from pathlib import Path
from typing import Dict, Any, Optional


# ============================================================================
# Logging Configuration
# ============================================================================

def configure_logging(log_dir: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        log_dir: Optional directory to write log files. If None, logs only to console.
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("video_agent")
    logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler (always present)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / "video_agent.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "video_agent") -> logging.Logger:
    """Get the configured logger instance."""
    return logging.getLogger(name)


# ============================================================================
# Telemetry (Metrics Collection)
# ============================================================================

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
