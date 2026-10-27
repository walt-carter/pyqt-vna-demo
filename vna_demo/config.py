"""Configuration-driven product definitions.

Adding a new part means adding an entry to products.json, not changing code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .instrument import SweepSettings


@dataclass(frozen=True)
class LimitSegment:
    """S21 must stay at or above ``min_db`` between start and stop frequency."""
    start_hz: float
    stop_hz: float
    min_db: float


@dataclass(frozen=True)
class Product:
    part_number: str
    description: str
    sweep: SweepSettings
    limits: tuple[LimitSegment, ...]


def load_products(path: str | Path) -> dict[str, Product]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    products: dict[str, Product] = {}
    for entry in raw["products"]:
        try:
            sweep = SweepSettings(
                start_hz=float(entry["sweep"]["start_hz"]),
                stop_hz=float(entry["sweep"]["stop_hz"]),
                points=int(entry["sweep"]["points"]),
            )
            sweep.validate()
            limits = tuple(
                LimitSegment(float(seg["start_hz"]), float(seg["stop_hz"]), float(seg["min_db"]))
                for seg in entry["limits"]
            )
            product = Product(entry["part_number"], entry.get("description", ""), sweep, limits)
        except (KeyError, TypeError, ValueError) as exc:
            name = entry.get("part_number", "<unnamed>") if isinstance(entry, dict) else "<invalid>"
            raise ValueError(f"Bad product definition for {name}: {exc}") from exc
        if product.part_number in products:
            raise ValueError(f"Duplicate part number: {product.part_number}")
        products[product.part_number] = product
    return products
