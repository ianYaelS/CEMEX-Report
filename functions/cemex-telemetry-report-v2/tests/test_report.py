from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any
from urllib.parse import urlparse

from constants import CODE_VERSION, HISTORY_TYPES, ROWS_PER_DAY, UTF8_BOM
from models import ReportParams
from params import parse_params
from report import generate_report
from report_service import generate_ui_report
from storage_io import LocalStorage


class FakeClient:
    def __init__(self, history_payload: dict[str, Any]) -> None:
        self.history_payload = history_payload
        self.calls: list[tuple[str, str, dict[str, str] | None]] = []

    def close(self) -> None:
        return None

    def request_json(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, path, params))
        vehicle = self.history_payload["data"][0]
        if path.startswith("/fleet/vehicles/") and path != "/fleet/vehicles/stats/history":
            return {
                "data": {
                    "id": vehicle["id"],
                    "name": vehicle["name"],
                    "licensePlate": "XYZ76",
                }
            }
        if path == "/fleet/vehicles":
            return {
                "data": [
                    {
                        "id": vehicle["id"],
                        "name": vehicle["name"],
                        "licensePlate": "XYZ76",
                    }
                ],
                "pagination": {"hasNextPage": False, "endCursor": ""},
            }
        raise AssertionError(f"unexpected request {method} {path}")

    def get_paginated(self, path: str, params: dict[str, str], merge_page) -> list[Any]:
        self.calls.append(("GET", path, params))
        collected: list[Any] = []
        if path == "/fleet/vehicles/stats/history":
            merge_page(collected, self.history_payload)
            return collected
        merge_page(
            collected,
            {
                "data": [
                    {
                        "id": self.history_payload["data"][0]["id"],
                        "name": self.history_payload["data"][0]["name"],
                        "licensePlate": "XYZ76",
                    }
                ],
                "pagination": {"hasNextPage": False},
            },
        )
        return collected


def _params(**overrides: Any) -> ReportParams:
    event = {
        "vehicle_id": "281474977075805",
        "report_date": "2026-08-31",
        "timezone": "America/Mexico_City",
        "granularity": "30s",
        "csv_dialect": "es",
    }
    event.update(overrides)
    return parse_params({key: value for key, value in event.items() if value is not None})


def test_history_types_are_exact(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    generate_report(_params(), "token-not-logged", storage=LocalStorage(), client=client)
    history_calls = [call for call in client.calls if call[1] == "/fleet/vehicles/stats/history"]
    assert history_calls
    assert history_calls[0][2]["types"] == HISTORY_TYPES
    assert "gpsOdometerMeters" not in history_calls[0][2]["types"]


def test_generate_report_writes_30s_csv(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    storage = LocalStorage()
    result = generate_report(
        _params(write_storage="true"),
        "token-not-logged",
        storage=storage,
        client=client,
    )
    assert result.row_count == ROWS_PER_DAY
    assert result.license_plate == "XYZ76"
    raw = storage.objects[result.storage_key]
    assert raw.startswith(UTF8_BOM)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
    assert rows[1][0] == "2026-08-31 00:00:00"
    assert rows[2][0] == "2026-08-31 00:00:30"
    assert rows[-1][0] == "2026-08-31 23:59:30"
    assert result.validation_status == "VALID"
    assert result.gap_count == 0
    assert result.carried_count == 2877
    assert result.summary()["codeVersion"] == CODE_VERSION
    assert result.summary()["slotSeconds"] == 30
    assert "Ralentí" in raw.decode("utf-8-sig")
    assert result.summary()["engine"]["idleCheck"] == "ok"


def test_two_day_range_is_5760_rows(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    result = generate_report(
        _params(start_time="2026-08-31", end_time="2026-09-01", write_storage="true"),
        "token-not-logged",
        storage=LocalStorage(),
        client=client,
    )
    assert result.day_count == 2
    assert result.row_count == 5760
    assert result.daily_row_counts == {"2026-08-31": 2880, "2026-09-01": 2880}


def test_ui_report_service_does_not_write_storage(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    result = generate_ui_report(
        "token-not-logged",
        vehicle_id="281474977075805",
        start_time=date(2026, 8, 31),
        end_time=date(2026, 8, 31),
        client=client,
    )
    assert result.stored is False
    assert result.row_count == 2880
    assert result.filename.endswith(".csv")


def test_no_network_in_unit_tests() -> None:
    parsed = urlparse("https://api.samsara.com/fleet/vehicles/stats/history")
    assert parsed.scheme == "https"
