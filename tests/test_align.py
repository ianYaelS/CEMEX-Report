from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from align import align_history, align_minute_window, collapse_to_minute
from models import GpsPoint, VehicleHistory, VehicleRef
from stats import parse_history
from transform import format_number, meters_to_km


def _history(payload: dict) -> object:
    vehicle = VehicleRef(id="281474977075805", name="FAV76")
    return parse_history(payload["data"][0], vehicle)


def test_obd_odometer_is_forward_filled(history_payload: dict) -> None:
    rows = align_history(_history(history_payload), "native", "America/Mexico_City")
    assert len(rows) == 3
    assert rows[0].odometer_meters == 227593015
    assert rows[1].odometer_meters == 227593015
    assert rows[2].odometer_meters == 228008850


def test_gps_odometer_trap_never_appears(history_payload: dict) -> None:
    rows = align_history(_history(history_payload), "native", "America/Mexico_City")
    values = {format_number(meters_to_km(row.odometer_meters)) for row in rows if row.odometer_meters is not None}
    assert "999999.999" not in values
    assert 999999999 not in {row.odometer_meters for row in rows}


def test_minute_keeps_last_gps_in_same_minute(history_payload: dict) -> None:
    history = _history(history_payload)
    collapsed = collapse_to_minute(history.gps, "America/Mexico_City")
    assert len(collapsed) == 2
    assert collapsed[0].time == history.gps[1].time
    assert collapsed[0].speed_mph == 1.0
    rows = align_history(history, "minute", "America/Mexico_City")
    assert len(rows) == 2
    assert rows[0].speed_mph == 1.0
    assert rows[1].speed_mph == 0.0


def test_minute_window_covers_full_local_day(history_payload: dict) -> None:
    tz = ZoneInfo("America/Mexico_City")
    start = datetime(2026, 8, 31, tzinfo=tz)
    end = datetime(2026, 9, 1, tzinfo=tz)
    rows = align_history(
        _history(history_payload),
        "minute",
        "America/Mexico_City",
        start=start,
        end=end,
    )
    assert len(rows) == 1440
    assert rows[0].time == start
    assert rows[-1].time == datetime(2026, 8, 31, 23, 59, tzinfo=tz)
    assert rows[0].latitude is not None
    assert rows[-1].latitude is not None
    assert all(row.latitude is not None for row in rows)
    nine = datetime(2026, 8, 31, 9, 0, tzinfo=tz)
    assert rows[0].latitude == next(row.latitude for row in rows if row.time == nine)


def test_parked_heartbeat_gaps_are_carried_continuously() -> None:
    tz = ZoneInfo("America/Mexico_City")
    start = datetime(2026, 8, 31, 7, 28, tzinfo=tz)
    end = datetime(2026, 8, 31, 7, 37, tzinfo=tz)
    history = VehicleHistory(
        vehicle=VehicleRef(id="1", name="FAV68"),
        gps=[
            GpsPoint(
                time=datetime(2026, 8, 31, 7, 29, tzinfo=tz),
                latitude=25.849268,
                longitude=-100.297851,
                speed_mph=0.0,
                address="Fidel Velázquez",
            ),
            GpsPoint(
                time=datetime(2026, 8, 31, 7, 31, tzinfo=tz),
                latitude=25.849407,
                longitude=-100.297628,
                speed_mph=0.0,
                address="Fidel Velázquez",
            ),
            GpsPoint(
                time=datetime(2026, 8, 31, 7, 36, tzinfo=tz),
                latitude=25.849407,
                longitude=-100.297628,
                speed_mph=0.0,
                address="Fidel Velázquez",
            ),
        ],
    )
    rows, _, _, carried = align_minute_window(history, "America/Mexico_City", start, end)
    assert [row.time.minute for row in rows] == [28, 29, 30, 31, 32, 33, 34, 35, 36]
    assert all(row.latitude is not None for row in rows)
    assert rows[0].latitude == 25.849268
    assert rows[4].latitude == 25.849407
    assert rows[4].time.minute == 32
    assert any(item["source"] == "forward" for item in carried)


def test_other_day_gps_is_not_out_of_range_for_daily_grid(history_payload: dict) -> None:
    tz = ZoneInfo("America/Mexico_City")
    history = _history(history_payload)
    later = history.gps[-1]
    history.gps.append(
        GpsPoint(
            time=datetime(2026, 9, 2, 12, 0, tzinfo=tz),
            latitude=later.latitude,
            longitude=later.longitude,
            speed_mph=later.speed_mph,
            address=later.address,
            is_ecu_speed=later.is_ecu_speed,
        )
    )
    start = datetime(2026, 8, 31, tzinfo=tz)
    end = datetime(2026, 9, 1, tzinfo=tz)
    rows, _, out_of_range, _ = align_minute_window(
        history, "America/Mexico_City", start, end
    )
    assert len(rows) == 1440
    assert out_of_range == 0
    assert all(row.latitude is not None for row in rows)


def test_second_forward_fills_between_first_and_last(history_payload: dict) -> None:
    history = _history(history_payload)
    rows = align_history(history, "second", "America/Mexico_City")
    first = history.gps[0].time.replace(microsecond=0)
    last = history.gps[-1].time.replace(microsecond=0)
    expected = int((last - first).total_seconds()) + 1
    assert len(rows) == expected
    assert rows[0].time == first
    assert rows[-1].time == last
    assert rows[1].time == first + timedelta(seconds=1)
    assert rows[1].latitude == history.gps[0].latitude
    assert rows[1].speed_mph == history.gps[0].speed_mph
    assert rows[-1].engine_raw == "Off"
    assert rows[0].engine_raw == "On"
