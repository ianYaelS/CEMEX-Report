from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "functions" / "cemex-telemetry-report-v2" / "src"))

from service import load_portal_config, report_payload
from models import ReportResult


def test_storage_link_points_to_cemex_function() -> None:
    config = load_portal_config()
    assert config["functionName"] == "cemex-telemetry-report-ui"
    assert "view=storage" in config["storageUrl"]
    assert "11006658" in config["storageUrl"]


def test_report_payload_includes_compare_links() -> None:
    result = ReportResult(
        vehicle_id="1",
        vehicle_name="FAV68",
        license_plate="ABC",
        report_date="2026-08-31",
        start="2026-08-31T00:00:00-06:00",
        end="2026-09-01T00:00:00-06:00",
        timezone="America/Mexico_City",
        granularity="30s",
        csv_dialect="es",
        row_count=2880,
        storage_key="CEMEX_Reportes/FAV68/2026-08-31_1_FAV68.csv",
        summary_key="",
        filename="2026-08-31_1_FAV68.csv",
        csv_bytes=b"\xef\xbb\xbfFecha",
        validation_status="VALID",
    )
    payload = report_payload(result)
    assert payload["ok"] is True
    assert payload["filename"].endswith(".csv")
    assert "view=storage" in payload["storageUrl"]
    assert payload["csv"].startswith("Fecha") or "Fecha" in payload["csv"]
    assert date.fromisoformat("2026-08-31")
