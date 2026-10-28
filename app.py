"""Entry point.

    python app.py                       # simulated VNA
    python app.py --visa TCPIP0::192.168.1.50::inst0::INSTR
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from vna_demo.config import load_products
from vna_demo.instrument import SimulatedVNA, VisaVNA
from vna_demo.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description="PyQt VNA test demo")
    parser.add_argument("--config", default=Path(__file__).parent / "config" / "products.json")
    parser.add_argument("--visa", metavar="RESOURCE", help="VISA resource string for a real VNA")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    try:
        products = load_products(args.config)
        instrument = VisaVNA(args.visa) if args.visa else SimulatedVNA()
    except (OSError, ValueError, ImportError) as exc:
        QMessageBox.critical(None, "Startup error", str(exc))
        return 1

    window = MainWindow(instrument, products)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
