"""Pass/fail evaluation against limit lines. No Qt here, so it's easy to unit test."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import LimitSegment


@dataclass(frozen=True)
class Result:
    passed: bool
    worst_margin_db: float     # most negative = worst; < 0 means a failure
    worst_freq_hz: float
    failing_points: int


def evaluate(freq_hz: np.ndarray, s21_db: np.ndarray, limits: tuple[LimitSegment, ...]) -> Result:
    if freq_hz.shape != s21_db.shape:
        raise ValueError("Frequency and data arrays must be the same length.")

    worst_margin = np.inf
    worst_freq = float("nan")
    failing = 0
    for seg in limits:
        mask = (freq_hz >= seg.start_hz) & (freq_hz <= seg.stop_hz)
        if not mask.any():
            continue
        margin = s21_db[mask] - seg.min_db
        failing += int((margin < 0).sum())
        i = int(np.argmin(margin))
        if margin[i] < worst_margin:
            worst_margin = float(margin[i])
            worst_freq = float(freq_hz[mask][i])

    if worst_margin == np.inf:
        raise ValueError("No measured points fall inside any limit segment.")
    return Result(failing == 0, worst_margin, worst_freq, failing)
