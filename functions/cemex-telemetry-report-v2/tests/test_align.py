from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from align import align_history, align_slot_window, collapse_to_slot
from models import GpsPoint, VehicleHistory, VehicleRef
from stats import parse_history


def _history(payload: dict) -> VehicleHistory:
    return parse_history(
        payload["data"][0],
        VehicleRef(id="281474977075805", name="FAV76"),
    )


def test_30s_window_covers_full_local_day(history_payload: dict) -> None:
    tz = ZoneInfo("America/Mexico_City")
    start = datetime(2026, 8, 31, tzinfo=tz)
    end = datetime(2026, 9, 1, tzinfo=tz)
    rows = align_history(
        _history(history_payload),
        "30s",
        "America/Mexico_City",
        start=start,
        end=end,
    )
    assert len(rows) == 2880
    assert rows[0].time == start
    assert rows[1].time == start + timedelta(seconds=30)
    assert rows[-1].time == datetime(2026, 8, 31, 23, 59, 30, tzinfo=tz)
    assert all(row.latitude is not None for row in rows)


def test_same_30s_slot_keeps_last_gps() -> None:
    tz = ZoneInfo("America/Mexico_City")
    history = VehicleHistory(
        vehicle=VehicleRef(id="1", name="X"),
        gps=[
            GpsPoint(
                time=datetime(2026, 8, 31, 9, 0, 5, tzinfo=tz),
                latitude=1.0,
                longitude=2.0,
                speed_mph=10.0,
                address="a",
            ),
            GpsPoint(
                time=datetime(2026, 8, 31, 9, 0, 20, tzinfo=tz),
                latitude=1.1,
                longitude=2.1,
                speed_mph=1.0,
                address="b",
            ),
        ],
    )
    collapsed = collapse_to_slot(history.gps, "America/Mexico_City", 30)
    assert len(collapsed) == 1
    assert collapsed[0].speed_mph == 1.0
    start = datetime(2026, 8, 31, 9, 0, tzinfo=tz)
    end = datetime(2026, 8, 31, 9, 1, tzinfo=tz)
    rows, collapsed_audit, _, _ = align_slot_window(
        history, "America/Mexico_City", start, end, slot_seconds=30
    )
    assert len(rows) == 2
    assert rows[0].speed_mph == 1.0
    assert collapsed_audit[0]["count"] == 2


def test_parked_heartbeat_gaps_are_carried_on_30s_grid() -> None:
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
        ],
    )
    rows, _, _, carried = align_slot_window(
        history, "America/Mexico_City", start, end, slot_seconds=30
    )
    assert len(rows) == 18
    assert rows[0].time.second in {0, 30}
    assert all(row.latitude is not None for row in rows)
    assert any(item["source"] == "leading" for item in carried)
    assert any(item["source"] == "forward" for item in carried)
