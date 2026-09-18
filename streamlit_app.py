"""Entrada para Streamlit Cloud / Docker: el cliente solo abre la URL."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "functions" / "cemex-telemetry-report-v2"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "ui"))

from app import main

main()
