"""Estimated Time of Arrival (ETA) calculator and formatter."""

from __future__ import annotations

import time


class Eta:
    def __init__(self, total_items: int) -> None:
        self.total = max(1, total_items)
        self.start_time = time.time()
        self.done = 0

    def update(self, done: int) -> None:
        self.done = max(0, min(self.total, done))

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def eta_seconds(self) -> float | None:
        if self.done <= 0:
            return None
        rate = self.done / self.elapsed
        remaining = self.total - self.done
        return remaining / rate

    def formatted_status(self) -> str:
        eta = self.eta_seconds
        el_str = format_seconds(self.elapsed)
        if eta is None:
            return f"Elapsed: {el_str}"
        return f"Elapsed: {el_str} | ETA: {format_seconds(eta)}"


def format_seconds(seconds: float) -> str:
    secs = int(round(seconds))
    mins, s = divmod(secs, 60)
    hrs, m = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs:d}h {m:02d}m {s:02d}s"
    if m > 0:
        return f"{m:d}m {s:02d}s"
    return f"{s:d}s"
