"""Abre la UI Streamlit en el navegador, precargada con config/params.json."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "ui" / "app.py"


def main() -> int:
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP),
            "--server.headless",
            "false",
            "--browser.gatherUsageStats",
            "false",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
