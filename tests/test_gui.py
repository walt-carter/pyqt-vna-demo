from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from vna_demo.config import load_products
from vna_demo.instrument import SimulatedVNA
from vna_demo.main_window import MainWindow

CONFIG = Path(__file__).parent.parent / "config" / "products.json"


@pytest.mark.parametrize("part, verdict", [("CABLE-0.5M-DEMO", "PASS"), ("CABLE-1M-DEMO", "FAIL")])
def test_sweep_shows_verdict(qtbot, part, verdict):
    window = MainWindow(SimulatedVNA(sweep_time_s=0, seed=3), load_products(CONFIG))
    qtbot.addWidget(window)
    window.part_combo.setCurrentText(part)

    window.start_sweep()

    qtbot.waitUntil(lambda: window.verdict.text() == verdict, timeout=5000)
    qtbot.waitUntil(lambda: window.run_button.isEnabled(), timeout=5000)  # thread cleaned up
