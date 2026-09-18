from __future__ import annotations

from datetime import date

from constants import DEFAULT_CSV_DIALECT, DEFAULT_GRANULARITY, DEFAULT_TIMEZONE
from models import ReportResult
from params import parse_params
from report import generate_report
from storage_io import LocalStorage


def generate_ui_report(
    token: str,
    *,
    vehicle_id: str,
    start_time: date,
    end_time: date,
    timezone: str = DEFAULT_TIMEZONE,
    client=None,
) -> ReportResult:
    params = parse_params(
        {
            "vehicle_id": vehicle_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "timezone": timezone,
            "granularity": DEFAULT_GRANULARITY,
            "csv_dialect": DEFAULT_CSV_DIALECT,
            "write_storage": "false",
            "include_csv": "false",
        }
    )
    return generate_report(params, token, storage=LocalStorage(), client=client)
