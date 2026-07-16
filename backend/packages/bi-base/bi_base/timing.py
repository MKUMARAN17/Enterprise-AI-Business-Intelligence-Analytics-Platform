"""A tiny wall-clock timer used to populate AUDIT_LOG.EXECUTION_MS and to meet
the non-functional requirement (< 5s for normal analytical queries) — we measure
so we can alert on regressions."""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Elapsed:
    ms: float = 0.0


@contextmanager
def stopwatch():
    """Context manager yielding an :class:`Elapsed` whose ``ms`` is filled on exit."""
    e = Elapsed()
    start = time.perf_counter()
    try:
        yield e
    finally:
        e.ms = round((time.perf_counter() - start) * 1000.0, 2)
