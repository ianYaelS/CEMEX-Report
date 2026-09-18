from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from align import align_minute_window
from minute_audit import VALID, audit_minute_grid
from models import GpsPoint, VehicleHistory, VehicleRef
from stats import parse_history
from timeutil import parse_api_time


def test_minute_grid_is_1440_unique_and_in_range(history_payload: dict) -> None:
    tz = ZoneInfo("America/Mexico_City")
    start = datetime(2026, 8, 31, tzinfo=tz)
    end = datetime(2026, 9, 1, tzinfo=tz)
    history = parse_history(
        history_payload["data"][0],
        VehicleRef(id="1", name="FAV76"),
    )
    rows, collapsed, out_of_range, carried = align_minute_window(
        history, "America/Mexico_City", start, end
    )
    audit = audit_minute_grid(
        rows,
        start=start,
        end=end,
        timezone="America/Mexico_City",
        collapsed_minutes=collapsed,
        carried_minutes=carried,
        out_of_range_count=out_of_range,
    )
    assert audit.row_count == 1440
    assert audit.unique_timestamps == 1440
    assert audit.first_timestamp == "2026-08-31 00:00"
    assert audit.last_timestamp == "2026-08-31 23:59"
    assert audit.grid["noMissingOutputMinute"]
    assert audit.grid["noDuplicateOutputMinute"]
    assert audit.grid["allTimestampsInRange"]
    assert audit.grid["noEmptyCells"]
    assert audit.status == VALID
    assert audit.gap_count == 0
    assert audit.native_count == 2
    assert audit.carried_count == 1438
    assert collapsed[0]["count"] == 2
    assert collapsed[0]["rule"] == "last_gps_by_timestamp"


def test_complete_coverage_is_valid() -> None:
    tz = ZoneInfo("America/Mexico_City")
    start = datetime(2026, 8, 31, 10, 0, tzinfo=tz)
    end = datetime(2026, 8, 31, 10, 2, tzinfo=tz)
    points = [
        GpsPoint(
            time=parse_api_time("2026-08-31T16:00:10Z"),
            latitude=1,
            longitude=2,
            speed_mph=0,
            address="",
        ),
        GpsPoint(
            time=parse_api_time("2026-08-31T16:01:10Z"),
            latitude=1,
            longitude=2,
            speed_mph=0,
            address="",
        ),
    ]
    history = VehicleHistory(vehicle=VehicleRef(id="1", name="X"), gps=points)
    rows, collapsed, _, _ = align_minute_window(history, "America/Mexico_City", start, end)
    audit = audit_minute_grid(
        rows,
        start=start,
        end=end,
        timezone="America/Mexico_City",
        collapsed_minutes=collapsed,
    )
    assert len(rows) == 2
    assert audit.status == VALID
    assert audit.gaps == []
