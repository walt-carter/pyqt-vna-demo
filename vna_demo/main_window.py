"""Operator-facing window: pick a part, run a sweep, see the trace and PASS/FAIL."""

from __future__ import annotations

from datetime import datetime

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import Product
from .instrument import Instrument
from .worker import SweepWorker


class MainWindow(QMainWindow):
    def __init__(self, instrument: Instrument, products: dict[str, Product]):
        super().__init__()
        self.setWindowTitle("VNA Test Demo")
        self.resize(1000, 700)
        self._instrument = instrument
        self._products = products
        self._thread: QThread | None = None
        self._worker: SweepWorker | None = None

        # Controls
        self.part_combo = QComboBox()
        self.part_combo.addItems(sorted(products))
        self.part_combo.currentTextChanged.connect(self._show_description)
        self.description = QLabel()
        self.run_button = QPushButton("Run sweep")
        self.run_button.clicked.connect(self.start_sweep)
        self.verdict = QLabel("READY")
        self.verdict.setStyleSheet("font-size: 28px; font-weight: bold; padding: 4px 16px;")

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Part:"))
        controls.addWidget(self.part_combo)
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
        self._show_description(self.part_combo.currentText())

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

    # ---- sweep lifecycle ----------------------------------------------
    def start_sweep(self) -> None:
        if self._thread is not None:
            return  # a sweep is already running
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

    def _plot(self, product: Product, freq, s21) -> None:
        self.ax.clear()
        self.ax.plot(freq / 1e9, s21, label="S21 (measured)", linewidth=1.2)
        for i, seg in enumerate(product.limits):
            self.ax.plot([seg.start_hz / 1e9, seg.stop_hz / 1e9], [seg.min_db, seg.min_db],
                         color="red", linestyle="--", linewidth=1.5,
                         label="Limit" if i == 0 else None)
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
