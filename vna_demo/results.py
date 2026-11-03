"""Handle results from the tests, like logging to a CSV file."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

import numpy as np
import csv
import re


from .analysis import Result
from .config import Product


def write_csv(
        path: Path,
        product: Product,
        serial: str,
        freq_hz: np.ndarray,
        s21_db: np.ndarray,
        result: Result,
) -> None:
    """Write the results to a CSV file"""

    # Make sure the frequency and s21_db arrays are the same length

    if len(freq_hz) != len(s21_db):
        raise ValueError(
            f"Frequency and S21 arrays differ in length ({len(freq_hz)} vs {len(s21_db)}.")
    
    # build a metadata block

    metadata = {
        "part_number": product.part_number,
        "description": product.description,
        "serial": serial,
        "timestamp": f"{datetime.now().astimezone():%Y-%m-%dT%H:%M:%S%z}",
        "sweep": f"{product.sweep.start_hz / 1e9:.3f}-{product.sweep.stop_hz / 1e9:.3f} GHz, {product.sweep.points} points",
        "verdict": f"{'PASS' if result.passed else 'FAIL'}",
        "worst_margin_db": f"{result.worst_margin_db:+.3f}",
        "worst_freq_ghz": f"{result.worst_freq_hz / 1e9:.3f}"
    }

    with open(path, "w", newline="", encoding="utf-8") as f:
        for key, value in metadata.items():
            f.write(f"# {key}: {value}\n")

        writer = csv.writer(f)
        writer.writerow(["frequency_hz", "s21_db"])
        writer.writerows(zip(freq_hz, s21_db))
    return


def result_path(results_dir: Path, part_number: str, serial: str,
                when: datetime | None = None) -> Path:
    """Pick a filename based on part number, serial, and date/timestamp"""

    when = when or datetime.now().astimezone()
    # no colons: Windows forbids them in filenames
    stamp = when.strftime("%Y%m%d-%H%M%S")
    safe = lambda s: re.sub(r"[^A-Za-z0-9._-]", "_", s)
    path = results_dir / f"{safe(part_number)}_{safe(serial)}_{stamp}.csv"
    n = 1
    # never overwrite, even for two runs in one second
    while path.exists():
        path = path.with_stem(f"{path.stem}_{n}")
        n += 1
    return path
