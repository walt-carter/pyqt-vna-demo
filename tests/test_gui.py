from pathlib import Path
import pytest
from PyQt6.QtCore import Qt
from vna_demo.config import load_products
from vna_demo.instrument import SimulatedVNA
from vna_demo.main_window import MainWindow

pytest.importorskip("PyQt6")


CONFIG = Path(__file__).parent.parent / "config" / "products.json"
RESULTS_DIR = Path(__file__).parent.parent / "results"


@pytest.mark.parametrize("part, verdict", [("CABLE-0.5M-DEMO", "PASS"),
                                           ("CABLE-1M-DEMO", "FAIL")])
def test_sweep_shows_verdict(qtbot, part, verdict):
    window = MainWindow(SimulatedVNA(sweep_time_s=0, seed=3),
                        load_products(CONFIG), RESULTS_DIR)
    qtbot.addWidget(window)
    window.part_combo.setCurrentText(part)
    window.serial_edit.setText("SPAM")
    window.start_sweep()

    # thread cleaned up
    qtbot.waitUntil(lambda: window.verdict.text() == verdict, timeout=5000)
    qtbot.waitUntil(lambda: window.run_button.isEnabled(), timeout=5000)


@pytest.fixture
def window(qtbot, tmp_path):
    win = MainWindow(SimulatedVNA(sweep_time_s=0, seed=3),
                     load_products(CONFIG), RESULTS_DIR)
    qtbot.addWidget(win)
    win.part_combo.setCurrentText("CABLE-0.5M-DEMO")
    return win


def test_run_disabled_until_serial_entered(qtbot, window):
    assert not window.run_button.isEnabled()
    qtbot.keyClicks(window.serial_edit, "SN-001")
    assert window.run_button.isEnabled()


def test_whitespace_only_serial_keeps_run_disabled(qtbot, window):
    qtbot.keyClicks(window.serial_edit, "   ")
    assert not window.run_button.isEnabled()


def test_enter_in_serial_box_starts_sweep(qtbot, window):
    qtbot.keyClicks(window.serial_edit, "SN-002")
    qtbot.keyClick(window.serial_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: window.verdict.text() == "PASS", timeout=5000)


def test_serial_locked_during_sweep_then_ready_for_next(qtbot, window):
    window._instrument.sweep_time_s = 0.5          # slow enough to observe the "running" state
    qtbot.keyClicks(window.serial_edit, "SN-003")
    window.start_sweep()
    assert not window.serial_edit.isEnabled()      # locked while sweeping
    assert not window.run_button.isEnabled()

    qtbot.waitUntil(lambda: window.serial_edit.isEnabled(), timeout=5000)
    assert window.serial_edit.selectedText() == "SN-003"
   # selected, so the next scan replaces it
    assert window.run_button.isEnabled()
