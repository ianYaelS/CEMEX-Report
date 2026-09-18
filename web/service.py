from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "functions" / "cemex-telemetry-report-v2"
sys.path.insert(0, str(V2 / "src"))

from client import SamsaraClient
from constants import DEFAULT_API_BASE_URL, DEFAULT_CSV_DIALECT, DEFAULT_GRANULARITY, DEFAULT_TIMEZONE
from models import ReportResult
from params import parse_params
from report import generate_report
from storage_io import LocalStorage
from vehicles import list_vehicles, vehicle_label

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_portal_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def list_fleet(token: str) -> list[dict[str, str]]:
    client = SamsaraClient(DEFAULT_API_BASE_URL, token)
    try:
        vehicles = list_vehicles(client)
    finally:
        client.close()
    return [
        {
            "id": vehicle.id,
            "name": vehicle.name,
            "licensePlate": vehicle.license_plate,
            "label": vehicle_label(vehicle),
        }
        for vehicle in vehicles
    ]


def build_report(
    token: str,
    *,
    vehicle_id: str,
    start_time: date,
    end_time: date,
    client: Any | None = None,
) -> ReportResult:
    params = parse_params(
        {
            "vehicle_id": vehicle_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "timezone": DEFAULT_TIMEZONE,
            "granularity": DEFAULT_GRANULARITY,
            "csv_dialect": DEFAULT_CSV_DIALECT,
            "write_storage": "false",
            "include_csv": "false",
        }
    )
    return generate_report(params, token, storage=LocalStorage(), client=client)


def report_payload(result: ReportResult) -> dict[str, Any]:
    config = load_portal_config()
    return {
        "ok": True,
        "filename": result.filename,
        "storageKey": result.storage_key,
        "rowCount": result.row_count,
        "validationStatus": result.validation_status,
        "vehicleId": result.vehicle_id,
        "vehicleName": result.vehicle_name,
        "licensePlate": result.license_plate,
        "period": {"start": result.start, "end": result.end},
        "storageUrl": config["storageUrl"],
        "functionUrl": config["functionUrl"],
        "message": (
            f"Se generó {result.filename}. El mismo archivo queda en Storage de Samsara "
            f"({result.storage_key}) cuando corre la Function cemex-telemetry-report-ui. "
            "Ábrelo y compáralo con la descarga."
        ),
        "csv": result.csv_text(),
    }
