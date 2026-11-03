"""Entry point.

python app.py                       # simulated VNA
python app.py --visa TCPIP0::192.168.1.50::inst0::INSTR
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

from pathlib import Path

from platformdirs import user_data_dir
from PyQt6.QtWidgets import QApplication, QMessageBox

from vna_demo.config import load_products
from vna_demo.instrument import SimulatedVNA, VisaVNA
from vna_demo.main_window import MainWindow

APP_NAME = "VNA-Test-Demo"


def config_dir() -> Path:
    """Editable config lives next to the executable in a build,
    and in the repo when run from source."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "config"
    return Path(__file__).parent / "config"


def resource_dir() -> Path:
    """
    Folder holding bundled data files, both when run from source
    and a Pyinstaller build
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def default_data_dir() -> Path:
    """Results folder: beside the app if writable, otherwise the per-user data folder."""
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).parent / "results"
    else:
        candidate = Path(__file__).parent / "results"

    try:
        candidate.mkdir(parents=True, exist_ok=True)
        if os.access(candidate, os.W_OK):
            return candidate
    except OSError:
        pass
    return Path(user_data_dir(APP_NAME, appauthor=False)) / "results"


def main() -> int:
    parser = argparse.ArgumentParser(description="PyQt VNA test demo")
    parser.add_argument(
        "--config", default=config_dir().parent / "config" / "products.json"
    )
    parser.add_argument(
        "--visa", metavar="RESOURCE", help="VISA resource string for a real VNA"
    )
    parser.add_argument("--results-dir", type=Path, default=default_data_dir())

    args = parser.parse_args()

    app = QApplication(sys.argv)
    try:
        products = load_products(args.config)
        instrument = VisaVNA(args.visa) if args.visa else SimulatedVNA()
    except (OSError, ValueError, ImportError) as exc:
        QMessageBox.critical(None, "Startup error", str(exc))
        return 1

    window = MainWindow(instrument, products, args.results_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
