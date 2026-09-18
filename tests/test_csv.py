from __future__ import annotations

import csv
import io

from constants import CSV_HEADERS_ES, UTF8_BOM
from csv_writer import render_csv
from models import AlignedRow, VehicleRef
from stats import parse_history
from timeutil import parse_api_time


def test_csv_bom_and_exact_spanish_headers() -> None:
    rows = [
        AlignedRow(
            time=parse_api_time("2026-08-31T15:00:40Z"),
            latitude=19.433,
            longitude=-99.133,
            speed_mph=1.0,
            address="Av. Paseo de la Reforma 2, CDMX",
            engine_raw="On",
            odometer_meters=227593015,
        )
    ]
    raw = render_csv(rows, "America/Mexico_City", "es")
    assert raw.startswith(UTF8_BOM)
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0].count(";") == 6
    assert '"Estado de motor (Encendido, Apagado, Ralentí)"' in text.splitlines()[0]
    parsed = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert parsed[0] == list(CSV_HEADERS_ES)
    assert parsed[0][1] == "Estado de motor (Encendido, Apagado, Ralentí)"
    assert "," in parsed[0][1]
    assert parsed[1][1] == "Encendido"
    assert parsed[1][2] == "1.61"
    assert parsed[1][3] == "19.433000"
    assert parsed[1][5] == "227593.02"
    assert parsed[1][6] == "Av. Paseo de la Reforma 2, CDMX"


def test_tracking_csv_matches_24h_headers() -> None:
    from constants import CSV_HEADERS_TRACKING

    rows = [
        AlignedRow(
            time=parse_api_time("2026-08-31T15:00:40Z"),
            latitude=19.433,
            longitude=-99.133,
            speed_mph=1.0,
            address="",
            engine_raw="Idle",
            odometer_meters=227593015,
        )
    ]
    raw = render_csv(rows, "America/Mexico_City", "tracking")
    assert not raw.startswith(UTF8_BOM)
    text = raw.decode("utf-8")
    parsed = list(csv.reader(text.splitlines()))
    assert parsed[0] == list(CSV_HEADERS_TRACKING)
    assert parsed[1][0].endswith(" CST")
    assert parsed[1][1] == "On (Idle)"
    assert parsed[1][6] == ""
    assert "227593.015" in parsed[1][5]


def test_parsed_history_ignores_gps_odometer(history_payload: dict) -> None:
    history = parse_history(
        history_payload["data"][0],
        VehicleRef(id="281474977075805", name="FAV76"),
    )
    assert [event.meters for event in history.obd_odometer] == [227593015, 228008850]
    assert not any(event.meters == 999999999 for event in history.obd_odometer)
