"""Tests for CSV export: file contents, filenames, and the results folder."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from vna_demo.analysis import Result
from vna_demo.config import load_products
from vna_demo.results import result_path, write_csv

CONFIG = Path(__file__).parent.parent / "config" / "products.json"


# ---- helpers / fixtures ---------------------------------------------------


def read_back(path: Path) -> tuple[dict[str, str], list[str], np.ndarray]:
    """Parse a results CSV: '# key: value' lines, a column header, then numeric rows."""
    metadata, data_lines = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            key, _, value = line[1:].partition(":")
            metadata[key.strip()] = value.strip()
        else:
            data_lines.append(line)
    header = data_lines[0].split(",")
    data = np.array([[float(x) for x in row.split(",")] for row in data_lines[1:]])
    return metadata, header, data


@pytest.fixture
def sample():
    product = load_products(CONFIG)["CABLE-0.5M-DEMO"]
    freq = np.array([10e6, 20e9, 40e9])
    s21 = np.array([-0.0312, -1.2345, -1.9876])
    result = Result(
        passed=True, worst_margin_db=0.52, worst_freq_hz=40e9, failing_points=0
    )
    return product, freq, s21, result


# ---- write_csv ------------------------------------------------------------


def test_round_trip_metadata_and_data(tmp_path, sample):
    product, freq, s21, result = sample
    path = tmp_path / "out.csv"
    write_csv(path, product, "SN-001", freq, s21, result)

    metadata, header, data = read_back(path)
    assert metadata["part_number"] == "CABLE-0.5M-DEMO"
    assert metadata["serial"] == "SN-001"
    assert header == ["frequency_hz", "s21_db"]
    assert data.shape == (3, 2)
    np.testing.assert_allclose(data[:, 0], freq)
    np.testing.assert_allclose(
        data[:, 1], s21, atol=1e-4
    )  # matches the precision you write


def test_verdict_recorded(tmp_path, sample):
    product, freq, s21, result = sample
    path = tmp_path / "out.csv"
    write_csv(path, product, "SN-001", freq, s21, result)
    metadata, _, _ = read_back(path)
    assert metadata["verdict"] == "PASS"  # or "verdict" == "PASS", whatever you chose


def test_timestamp_keeps_colons_inside_file(tmp_path, sample):
    """Splitting on the first colon only must preserve ISO timestamps."""
    product, freq, s21, result = sample
    path = tmp_path / "out.csv"
    write_csv(path, product, "SN-001", freq, s21, result)
    metadata, _, _ = read_back(path)
    datetime.fromisoformat(metadata["timestamp"])  # raises if it was mangled


def test_no_blank_lines_between_rows(tmp_path, sample):
    """Catches the classic Windows newline='' bug (\\r\\r\\n between rows)."""
    product, freq, s21, result = sample
    path = tmp_path / "out.csv"
    write_csv(path, product, "SN-001", freq, s21, result)
    raw = path.read_bytes()
    assert b"\r\r\n" not in raw
    assert all(line.strip() for line in raw.decode("utf-8").splitlines())


def test_non_ascii_description_survives(tmp_path, sample):
    """Explicit UTF-8: a µ or O must read back the same on Windows and Linux."""
    _, freq, s21, result = sample
    product = load_products(CONFIG)["CABLE-0.5M-DEMO"]
    path = tmp_path / "out.csv"
    write_csv(path, product, "SN-µO-7", freq, s21, result)
    metadata, _, _ = read_back(path)
    assert metadata["serial"] == "SN-µO-7"


def test_mismatched_arrays_rejected(tmp_path, sample):
    product, freq, _, result = sample
    path = tmp_path / "out.csv"
    with pytest.raises(ValueError, match="differ in length"):
        write_csv(path, product, "SN-001", freq, np.zeros(2), result)

    assert not path.exists()


# ---- result_path ----------------------------------------------------------

FIXED = datetime(2026, 11, 2, 15, 5, 33, tzinfo=timezone(timedelta(hours=-6)))


def test_filename_format(tmp_path):
    path = result_path(tmp_path, "CABLE-0.5M-DEMO", "SN-001", when=FIXED)
    assert path.parent == tmp_path
    assert path.name == "CABLE-0.5M-DEMO_SN-001_20261102-150533.csv"


@pytest.mark.parametrize("bad_serial", ["SN/001", "SN:001", "SN 001", "SN\\001"])
def test_filename_is_windows_safe(tmp_path, bad_serial):
    path = result_path(tmp_path, "PART", bad_serial, when=FIXED)
    assert not set(path.name) & set('<>:"/\\|?* ')


def test_existing_file_never_overwritten(tmp_path):
    first = result_path(tmp_path, "PART", "SN-001", when=FIXED)
    first.write_text("existing", encoding="utf-8")
    second = result_path(tmp_path, "PART", "SN-001", when=FIXED)
    assert second != first
    assert not second.exists()
