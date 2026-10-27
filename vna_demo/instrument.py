"""Instrument layer.

The GUI only talks to the ``Instrument`` interface, so a simulated VNA and a
real one (through PyVISA) are interchangeable. That's the same separation you'd
want in a production test station: the process flow never knows or cares
which hardware is attached.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SweepSettings:
    start_hz: float
    stop_hz: float
    points: int

    def validate(self) -> None:
        if self.start_hz <= 0 or self.stop_hz <= self.start_hz:
            raise ValueError("Sweep must have 0 < start < stop.")
        if not 2 <= self.points <= 100_001:
            raise ValueError("Points must be between 2 and 100001.")


class Instrument(ABC):
    """Minimal VNA interface used by the application."""

    @abstractmethod
    def identify(self) -> str: ...

    @abstractmethod
    def configure(self, sweep: SweepSettings) -> None: ...

    @abstractmethod
    def measure_s21_db(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (frequency_hz, s21_db)."""

    def close(self) -> None:
        pass


class SimulatedVNA(Instrument):
    """Fake 2-port VNA that returns a plausible cable/connector S21 trace.

    Insertion loss is modeled as skin-effect loss (~sqrt(f)) plus dielectric
    loss (~f), with a small resonance ripple and measurement noise. ``seed``
    makes runs repeatable for tests.
    """

    def __init__(self, skin_coeff: float = 0.25, dielectric_coeff: float = 0.012,
                 noise_db: float = 0.05, sweep_time_s: float = 1.5, seed: int | None = None):
        self.skin_coeff = skin_coeff            # dB per sqrt(GHz)
        self.dielectric_coeff = dielectric_coeff  # dB per GHz
        self.noise_db = noise_db
        self.sweep_time_s = sweep_time_s
        self._rng = np.random.default_rng(seed)
        self._sweep: SweepSettings | None = None

    def identify(self) -> str:
        return "SIMULATED,VNA-DEMO,0001,1.0"

    def configure(self, sweep: SweepSettings) -> None:
        sweep.validate()
        self._sweep = sweep

    def measure_s21_db(self) -> tuple[np.ndarray, np.ndarray]:
        if self._sweep is None:
            raise RuntimeError("configure() must be called before measuring.")
        time.sleep(self.sweep_time_s)  # mimic a slow sweep so threading matters
        s = self._sweep
        f = np.linspace(s.start_hz, s.stop_hz, s.points)
        f_ghz = f / 1e9
        loss = self.skin_coeff * np.sqrt(f_ghz) + self.dielectric_coeff * f_ghz
        ripple = 0.15 * np.sin(2 * np.pi * f_ghz / 7.0)
        noise = self._rng.normal(0.0, self.noise_db, f.size)
        return f, -(loss + ripple + noise)


class VisaVNA(Instrument):
    """Real instrument over PyVISA, using generic SCPI.

    Exact SCPI commands vary by vendor (Keysight, R&S, Anritsu, Copper
    Mountain). These follow common Keysight-style syntax and are a starting
    point, not a tested driver.
    """

    def __init__(self, resource: str, timeout_ms: int = 30_000):
        import pyvisa  # imported here so the demo runs without PyVISA installed

        self._rm = pyvisa.ResourceManager()
        self._inst = self._rm.open_resource(resource)
        self._inst.timeout = timeout_ms

    def identify(self) -> str:
        return self._inst.query("*IDN?").strip()

    def configure(self, sweep: SweepSettings) -> None:
        sweep.validate()
        self._inst.write(f"SENS:FREQ:STAR {sweep.start_hz}")
        self._inst.write(f"SENS:FREQ:STOP {sweep.stop_hz}")
        self._inst.write(f"SENS:SWE:POIN {sweep.points}")
        self._inst.write("CALC:PAR:DEF 'demo_s21',S21")
        self._inst.write("CALC:PAR:SEL 'demo_s21'")
        self._inst.write("CALC:FORM MLOG")

    def measure_s21_db(self) -> tuple[np.ndarray, np.ndarray]:
        self._inst.write("INIT:IMM")
        self._inst.query("*OPC?")  # block until the sweep completes
        freq = np.array(self._inst.query_ascii_values("SENS:X?"))
        data = np.array(self._inst.query_ascii_values("CALC:DATA? FDATA"))
        return freq, data

    def close(self) -> None:
        self._inst.close()
        self._rm.close()
