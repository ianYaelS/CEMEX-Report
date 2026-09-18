from __future__ import annotations

import pytest

from constants import MPH_TO_KMH
from transform import format_number, map_engine_state, meters_to_km, mph_to_kmh


def test_one_mph_uses_exact_factor() -> None:
    assert 1 * MPH_TO_KMH == 1.609344
    assert mph_to_kmh(1) == 1.609344


def test_real_world_speed_to_ten_kmh() -> None:
    assert mph_to_kmh(6.213712) == pytest.approx(10.0, abs=1e-6)


def test_odometer_meters_to_km() -> None:
    assert meters_to_km(227593015) == pytest.approx(227593.015)
    assert format_number(meters_to_km(228008850)) == "228008.85"


def test_engine_on_variants_map_to_encendido() -> None:
    assert map_engine_state("On", "es") == "Encendido"
    assert map_engine_state("On (Driving)", "es") == "Encendido"


def test_engine_idle_maps_to_ralenti() -> None:
    assert map_engine_state("Idle", "es") == "Ralentí"
    assert map_engine_state("On (Idle)", "es") == "Ralentí"
    assert map_engine_state("Idle", "en") == "Idle"


def test_tracking_engine_preserves_idle_and_driving() -> None:
    from transform import map_engine_tracking

    assert map_engine_tracking("Off") == "Off"
    assert map_engine_tracking("Idle") == "On (Idle)"
    assert map_engine_tracking("On") == "On (Driving)"
    assert map_engine_tracking("On (Idle)") == "On (Idle)"


def test_engine_off_and_none_map_to_apagado() -> None:
    assert map_engine_state("Off", "es") == "Apagado"
    assert map_engine_state(None, "es") == "Apagado"
    assert map_engine_state("None", "es") == "Apagado"


def test_summarize_engine_flags_idle_in_api_and_csv(history_payload: dict) -> None:
    from align import align_minute_window
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from models import VehicleRef
    from stats import parse_history
    from transform import summarize_engine

    tz = ZoneInfo("America/Mexico_City")
    history = parse_history(history_payload["data"][0], VehicleRef(id="1", name="X"))
    rows, _, _, _ = align_minute_window(
        history,
        "America/Mexico_City",
        datetime(2026, 8, 31, tzinfo=tz),
        datetime(2026, 9, 1, tzinfo=tz),
    )
    summary = summarize_engine(history, rows, "es")
    assert summary["idleInApi"] is True
    assert summary["idleInCsv"] is True
    assert summary["idleCheck"] == "ok"
    assert summary["csvCounts"].get("Ralentí", 0) > 0
