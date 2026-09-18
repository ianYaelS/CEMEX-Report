from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "functions" / "cemex-telemetry-report" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "vehicle_stats.json"


@pytest.fixture
def history_payload() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
