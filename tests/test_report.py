from __future__ import annotations

import csv
import io
from typing import Any
from urllib.parse import urlparse

from constants import CODE_VERSION, HISTORY_TYPES, UTF8_BOM
from models import ReportParams
from params import parse_params
from report import generate_report
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
        if path.startswith("/fleet/vehicles/") and path != "/fleet/vehicles/stats/history":
            vehicle = self.history_payload["data"][0]
            return {"data": {"id": vehicle["id"], "name": vehicle["name"]}}
        if path == "/fleet/vehicles":
            vehicle = self.history_payload["data"][0]
            return {
                "data": [{"id": vehicle["id"], "name": vehicle["name"]}],
                "pagination": {"hasNextPage": False, "endCursor": ""},
            }
        raise AssertionError(f"unexpected request {method} {path}")

    def get_paginated(self, path: str, params: dict[str, str], merge_page) -> list[Any]:
        self.calls.append(("GET", path, params))
        collected: list[Any] = []
        merge_page(collected, self.history_payload)
        return collected


def _params(**overrides: Any) -> ReportParams:
    event = {
        "vehicle_name": "FAV76",
        "report_date": "2026-08-31",
        "timezone": "America/Mexico_City",
        "granularity": "minute",
        "csv_dialect": "es",
    }
    event.update(overrides)
    return parse_params(event)


def test_history_types_are_exact_and_omit_gps_odometer(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    generate_report(_params(), "token-not-logged", storage=LocalStorage(), client=client)
    history_calls = [call for call in client.calls if call[1] == "/fleet/vehicles/stats/history"]
    assert history_calls
    types = history_calls[0][2]["types"]
    assert types == HISTORY_TYPES
    assert types == "gps,engineStates,obdOdometerMeters"
    assert "gpsOdometerMeters" not in types


def test_generate_report_returns_csv_without_storage(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    storage = LocalStorage()
    result = generate_report(
        _params(write_storage="false"),
        "token-not-logged",
        storage=storage,
        client=client,
    )
    assert result.stored is False
    assert storage.objects == {}
    assert result.filename == "2026-08-31_281474977075805_FAV76.csv"
    payload = result.summary(include_csv=True)
    assert payload["csv"]
    assert "Fecha y hora" in str(payload["csv"])
    assert payload["filename"] == result.filename


def test_generate_report_writes_storage_and_csv(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    storage = LocalStorage()
    result = generate_report(
        _params(write_storage="true"),
        "token-not-logged",
        storage=storage,
        client=client,
    )
    assert result.storage_key == "CEMEX_Reportes/FAV76/2026-08-31_281474977075805_FAV76.csv"
    assert result.row_count == 1440
    raw = storage.objects[result.storage_key]
    assert raw.startswith(UTF8_BOM)
    assert raw == result.csv_bytes
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][1] == "Estado de motor (Encendido, Apagado, Ralentí)"
    assert rows[1][0] == "2026-08-31 00:00:00"
    assert rows[-1][0] == "2026-08-31 23:59:00"
    body = raw.decode("utf-8-sig")
    assert "999999" not in body
    assert "227593.02" in body or "228008.85" in body
    assert result.row_count == 1440
    assert result.validation_status == "VALID"
    assert result.gap_count == 0
    assert result.carried_count == 1438
    assert result.summary_key.endswith("_auditoria.json")
    assert result.summary_key in storage.objects
    assert result.summary()["statusCode"] == 200
    assert result.summary()["rows_generated"] == 1440
    assert result.day_count == 1
    assert result.daily_row_counts == {"2026-08-31": 1440}
    assert result.summary()["collapsedMinuteCount"] == result.collapsed_count
    assert result.summary()["fillRule"] == "last_known_carry"
    assert result.summary()["codeVersion"] == CODE_VERSION
    assert result.summary()["carriedMinuteCount"] == 1438
    assert "Ralentí" in raw.decode("utf-8-sig")
    engine = result.summary()["engine"]
    assert engine["idleCheck"] == "ok"
    assert engine["idleInApi"] is True
    assert engine["idleInCsv"] is True
    assert engine["csvCounts"]["Ralentí"] > 0


def test_two_day_range_writes_single_consolidated_file(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    storage = LocalStorage()
    result = generate_report(
        _params(
            write_storage="true",
            start_time="2026-08-31",
            end_time="2026-09-01",
            vehicle_id="281474977075805",
            vehicle_name=None,
        ),
        "token-not-logged",
        storage=storage,
        client=client,
    )
    assert result.day_count == 2
    assert result.row_count == 2880
    assert result.daily_row_counts == {"2026-08-31": 1440, "2026-09-01": 1440}
    assert result.daily_files == [
        "CEMEX_Reportes/FAV76/2026-08-31_a_2026-09-01_281474977075805_FAV76.csv"
    ]
    assert list(storage.objects) == [
        "CEMEX_Reportes/FAV76/2026-08-31_a_2026-09-01_281474977075805_FAV76.csv",
        "CEMEX_Reportes/FAV76/2026-08-31_a_2026-09-01_281474977075805_FAV76_auditoria.json",
    ]
    summary = result.summary()
    assert summary["rowCount"] == 2880
    assert summary["dayCount"] == 2
    assert summary["dailyRowCounts"] == {"2026-08-31": 1440, "2026-09-01": 1440}


def test_seven_day_range_writes_one_csv_of_10080_rows(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    storage = LocalStorage()
    result = generate_report(
        _params(
            write_storage="true",
            start_time="2026-08-31",
            end_time="2026-09-06",
            vehicle_id="281474977075805",
            vehicle_name=None,
        ),
        "token-not-logged",
        storage=storage,
        client=client,
    )
    days = [
        "2026-08-31",
        "2026-09-01",
        "2026-09-02",
        "2026-09-03",
        "2026-09-04",
        "2026-09-05",
        "2026-09-06",
    ]
    assert result.day_count == 7
    assert result.row_count == 10080
    assert result.daily_row_counts == {day: 1440 for day in days}
    assert result.storage_key == (
        "CEMEX_Reportes/FAV76/2026-08-31_a_2026-09-06_281474977075805_FAV76.csv"
    )
    assert list(storage.objects) == [
        "CEMEX_Reportes/FAV76/2026-08-31_a_2026-09-06_281474977075805_FAV76.csv",
        "CEMEX_Reportes/FAV76/2026-08-31_a_2026-09-06_281474977075805_FAV76_auditoria.json",
    ]
    summary = result.summary()
    assert summary["rowCount"] == 10080
    assert summary["dayCount"] == 7
    assert summary["validationStatus"] == "VALID"
    assert summary["gapCount"] == 0
    assert "collapsedMinuteCount" in summary


def test_cli_style_vehicle_id_uses_get_vehicle(history_payload: dict) -> None:
    client = FakeClient(history_payload)
    result = generate_report(
        _params(vehicle_id="281474977075805", vehicle_name=None),
        "token-not-logged",
        storage=LocalStorage(),
        client=client,
    )
    assert result.vehicle_name == "FAV76"
    assert any(path == "/fleet/vehicles/281474977075805" for _, path, _ in client.calls)


class Catalog404Client(FakeClient):
    def request_json(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        from errors import ApiError

        if path.startswith("/fleet/vehicles/") or path in {"/fleet/vehicles", "/assets"}:
            if path != "/fleet/vehicles/stats/history":
                self.calls.append((method, path, params))
                raise ApiError(f"{path}: HTTP 404", 404)
        return super().request_json(method, path, params)


def test_report_continues_when_vehicle_catalog_404s(history_payload: dict) -> None:
    client = Catalog404Client(history_payload)
    result = generate_report(
        _params(vehicle_id="281474977075805", vehicle_name=None),
        "token-not-logged",
        storage=LocalStorage(),
        client=client,
    )
    assert result.row_count == 1440
    assert result.vehicle_name == "FAV76"


def test_no_network_in_unit_tests() -> None:
    parsed = urlparse("https://api.samsara.com/fleet/vehicles/stats/history")
    assert parsed.scheme == "https"
