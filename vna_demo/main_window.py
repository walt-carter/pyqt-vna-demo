"""Operator-facing window: pick a part, run a sweep, see the trace and PASS/FAIL."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import Product
from .instrument import Instrument
from .results import result_path, write_csv
from .worker import SweepWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self, instrument: Instrument, products: dict[str, Product], results_dir: Path
    ):
        super().__init__()
        self.setWindowTitle("VNA Test Demo")
        self.resize(1000, 700)
        self._instrument = instrument
        self._products = products
        self._thread: QThread | None = None
        self._worker: SweepWorker | None = None

        # Make sure the results dir exists

        self._results_dir = results_dir
        self._results_dir.mkdir(parents=True, exist_ok=True)

        # Controls
        self.part_combo = QComboBox()
        self.part_combo.addItems(sorted(products))
        self.part_combo.currentTextChanged.connect(self._show_description)
        self.description = QLabel()
        self.run_button = QPushButton("Run sweep")
        self.run_button.clicked.connect(self.start_sweep)
        self.verdict = QLabel("READY")
        self.verdict.setStyleSheet(
            "font-size: 28px; font-weight: bold; padding: 4px 16px;"
        )
        self.serial_edit = QLineEdit()
        self.serial_edit.setPlaceholderText("Scan or type serial number")
        self.serial_edit.setClearButtonEnabled(True)
        self.serial_edit.returnPressed.connect(
            self.start_sweep
        )  # Enter starts the sweep
        self.serial_edit.textChanged.connect(self._update_run_enabled)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Part:"))
        controls.addWidget(self.part_combo)
        controls.addWidget(QLabel("Serial:"))
        controls.addWidget(self.serial_edit, stretch=1)  # let it take spare width
        controls.addWidget(self.run_button)
        controls.addStretch()
        controls.addWidget(self.verdict)

        # Plot
        self.figure = Figure(figsize=(8, 4), layout="tight")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot()

        # Log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.description)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.log)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._log(f"Connected: {instrument.identify()}")
        self._log(f"Results folder: {results_dir}")
        self._show_description(self.part_combo.currentText())
        self._update_run_enabled()

    # ---- helpers -------------------------------------------------------
    def _log(self, message: str) -> None:
        self.log.appendPlainText(f"{datetime.now():%H:%M:%S}  {message}")

    def _show_description(self, part: str) -> None:
        product = self._products.get(part)
        self.description.setText(product.description if product else "")

    def _set_verdict(self, text: str, color: str) -> None:
        self.verdict.setText(text)
        self.verdict.setStyleSheet(
            f"font-size: 28px; font-weight: bold; padding: 4px 16px; color: white; background: {color};"
        )

    def _update_run_enabled(self) -> None:
        running = self._thread is not None
        self.run_button.setEnabled(
            not running and bool(self.serial_edit.text().strip())
        )

    # ---- sweep lifecycle ----------------------------------------------
    def start_sweep(self) -> None:
        serial = self.serial_edit.text().strip()
        if self._thread is not None or not serial:
            return  # a sweep is already running
        self._current_serial = serial
        self.serial_edit.setEnabled(False)
        product = self._products[self.part_combo.currentText()]
        self.run_button.setEnabled(False)
        self.part_combo.setEnabled(False)
        self._set_verdict("TESTING", "#7a7a7a")

        self._thread = QThread()
        self._worker = SweepWorker(self._instrument, product)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self._log)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_finished(self, freq, s21, result) -> None:
        product = self._products[self.part_combo.currentText()]
        self._plot(product, freq, s21)
        if result.passed:
            self._set_verdict("PASS", "#2e7d32")
        else:
            self._set_verdict("FAIL", "#c62828")
            self._log(
                f"{product.part_number}: {'PASS' if result.passed else 'FAIL'} | "
                f"worst margin {result.worst_margin_db:+.2f} dB at {result.worst_freq_hz / 1e9:.2f} GHz | "
                f"{result.failing_points} failing point(s)"
            )

        path = result_path(
            self._results_dir, product.part_number, self._current_serial, None
        )
        try:
            write_csv(path, product, self._current_serial, freq, s21, result)
        except OSError:
            logger.exception("Could not save results to %s", path)
            self._log(f"Could not save results to  {path.name}")
        else:
            self._log(f"Saved {path.name}")

    def _on_failed(self, message: str) -> None:
        self._set_verdict("ERROR", "#e65100")
        self._log(f"Sweep error: {message}")

    def _cleanup_thread(self) -> None:
        self._worker.deleteLater()
        self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self.run_button.setEnabled(True)
        self.part_combo.setEnabled(True)
        self.serial_edit.setEnabled(True)
        self.serial_edit.selectAll()  # next scan or keystroke replaces the old serial
        self.serial_edit.setFocus()
        self._update_run_enabled()  # replaces run_button.setEnabled(True)

    def _plot(self, product: Product, freq, s21) -> None:
        self.ax.clear()
        self.ax.plot(freq / 1e9, s21, label="S21 (measured)", linewidth=1.2)
        for i, seg in enumerate(product.limits):
            self.ax.plot(
                [seg.start_hz / 1e9, seg.stop_hz / 1e9],
                [seg.min_db, seg.min_db],
                color="red",
                linestyle="--",
                linewidth=1.5,
                label="Limit" if i == 0 else None,
            )
        self.ax.set_xlabel("Frequency (GHz)")
        self.ax.set_ylabel("S21 (dB)")
        self.ax.set_title(f"{product.part_number} insertion loss")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc="lower left")
        self.canvas.draw_idle()

    def closeEvent(self, event) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
        self._instrument.close()
        super().closeEvent(event)
