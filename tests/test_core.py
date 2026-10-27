"""Unit tests for the Qt-free layers. Run with: python -m pytest"""

import json
from pathlib import Path

import numpy as np
import pytest

from vna_demo.analysis import evaluate
from vna_demo.config import LimitSegment, load_products
from vna_demo.instrument import SimulatedVNA, SweepSettings

CONFIG = Path(__file__).parent.parent / "config" / "products.json"


def test_sweep_settings_reject_bad_ranges():
    with pytest.raises(ValueError):
        SweepSettings(10e9, 1e9, 101).validate()
    with pytest.raises(ValueError):
        SweepSettings(1e9, 10e9, 1).validate()


def test_simulated_vna_returns_requested_points():
    vna = SimulatedVNA(sweep_time_s=0, seed=1)
    vna.configure(SweepSettings(10e6, 40e9, 801))
    f, s21 = vna.measure_s21_db()
    assert f.size == s21.size == 801
    assert f[0] == pytest.approx(10e6) and f[-1] == pytest.approx(40e9)
    assert s21[-1] < s21[0]  # loss grows with frequency


def test_simulated_vna_requires_configure():
    with pytest.raises(RuntimeError):
        SimulatedVNA(sweep_time_s=0).measure_s21_db()


def test_simulated_vna_is_repeatable_with_seed():
    a, b = SimulatedVNA(sweep_time_s=0, seed=7), SimulatedVNA(sweep_time_s=0, seed=7)
    sweep = SweepSettings(10e6, 20e9, 201)
    a.configure(sweep)
    b.configure(sweep)
    assert np.array_equal(a.measure_s21_db()[1], b.measure_s21_db()[1])


def test_evaluate_pass_and_fail():
    f = np.array([1e9, 2e9, 3e9])
    limits = (LimitSegment(0, 3e9, -1.0),)
    assert evaluate(f, np.array([-0.2, -0.5, -0.8]), limits).passed
    result = evaluate(f, np.array([-0.2, -1.5, -0.8]), limits)
    assert not result.passed
    assert result.failing_points == 1
    assert result.worst_freq_hz == 2e9
    assert result.worst_margin_db == pytest.approx(-0.5)


def test_evaluate_rejects_mismatched_arrays():
    with pytest.raises(ValueError):
        evaluate(np.zeros(3), np.zeros(4), (LimitSegment(0, 1, 0),))


def test_shipped_config_loads():
    products = load_products(CONFIG)
    assert "CABLE-0.5M-DEMO" in products
    assert all(p.limits for p in products.values())


def test_config_rejects_duplicates(tmp_path):
    entry = json.loads(CONFIG.read_text())["products"][0]
    bad = tmp_path / "dup.json"
    bad.write_text(json.dumps({"products": [entry, entry]}))
    with pytest.raises(ValueError, match="Duplicate"):
        load_products(bad)


def test_demo_parts_give_expected_verdicts():
    """The 0.5 m cable should pass and the 1 m cable (tight limit) should fail."""
    products = load_products(CONFIG)
    vna = SimulatedVNA(sweep_time_s=0, seed=3)
    for part, expected in [("CABLE-0.5M-DEMO", True), ("CABLE-1M-DEMO", False)]:
        p = products[part]
        vna.configure(p.sweep)
        f, s21 = vna.measure_s21_db()
        assert evaluate(f, s21, p.limits).passed is expected
