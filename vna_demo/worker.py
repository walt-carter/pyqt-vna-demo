"""Runs a sweep off the GUI thread.

Instrument calls can block for seconds. Doing them on the GUI thread freezes
the window, so the worker lives in a QThread and reports back through signals.
(The LabVIEW Actor Framework equivalent: a measurement actor sending messages
to the UI actor.)
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .analysis import evaluate
from .config import Product
from .instrument import Instrument


class SweepWorker(QObject):
    status = pyqtSignal(str)
    finished = pyqtSignal(object, object, object)  # freq_hz, s21_db, Result
    failed = pyqtSignal(str)

    def __init__(self, instrument: Instrument, product: Product):
        super().__init__()
        self._instrument = instrument
        self._product = product

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.status.emit(f"Configuring sweep for {self._product.part_number}...")
            self._instrument.configure(self._product.sweep)
            self.status.emit("Sweeping...")
            freq, s21 = self._instrument.measure_s21_db()
            result = evaluate(freq, s21, self._product.limits)
            self.finished.emit(freq, s21, result)
        except Exception as exc:  # report every failure to the operator, don't crash
            self.failed.emit(f"{type(exc).__name__}: {exc}")
