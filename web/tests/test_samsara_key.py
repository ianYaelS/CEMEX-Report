from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "functions" / "cemex-telemetry-report-v2" / "src"))

from storage_io import storage_object_key
from timeutil import local_day_bounds


def _js_sanitize(value: str, fallback: str = "unidad") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (value or "").strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("._") or fallback


def expected_storage_key(prefix: str, vehicle_id: str, vehicle_name: str, start: str, end: str) -> str:
    root = _js_sanitize(prefix, "CEMEX_Reportes")
    unit_id = _js_sanitize(vehicle_id, "sinid")
    unit_name = _js_sanitize(vehicle_name, unit_id)
    folder = unit_id if unit_name == "unidad" else unit_name
    stamp = start if start == end else f"{start}_a_{end}"
    return f"{root}/{folder}/{stamp}_{unit_id}_{unit_name}.csv"


def test_portal_points_to_cemex_function() -> None:
    config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
    assert config["functionName"] == "cemex-telemetry-report-ui"
    assert "view=storage" in config["storageUrl"]


def test_expected_key_matches_function_one_day() -> None:
    start, end = local_day_bounds(date(2026, 8, 31), "America/Mexico_City")
    function_key = storage_object_key(
        "CEMEX_Reportes",
        "FAV68",
        start,
        end,
        "30s",
        "America/Mexico_City",
        vehicle_id="281474977123456",
    )
    ui_key = expected_storage_key("CEMEX_Reportes", "281474977123456", "FAV68", "2026-08-31", "2026-08-31")
    assert ui_key == function_key
    assert ui_key.endswith("2026-08-31_281474977123456_FAV68.csv")
