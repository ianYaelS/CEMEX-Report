from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta
from typing import Any, TypeVar

from constants import FILL_RULE, GRID_SECONDS
from models import AlignedRow, GpsPoint, VehicleHistory
from timeutil import local_slot_key, truncate_to_second

T = TypeVar("T")

SAME_SLOT_RULE = "last_gps_by_timestamp"
SAME_MINUTE_RULE = SAME_SLOT_RULE


def _asof(times: list[datetime], values: list[T], at: datetime) -> T | None:
    if not times:
        return None
    idx = bisect_right(times, at) - 1
    if idx < 0:
        return None
    return values[idx]


def _sorted_gps(points: list[GpsPoint]) -> list[GpsPoint]:
    return sorted(points, key=lambda point: point.time)


def collapse_to_slot(
    points: list[GpsPoint],
    timezone: str,
    slot_seconds: int = GRID_SECONDS,
) -> list[GpsPoint]:
    last_by_slot: dict[datetime, GpsPoint] = {}
    for point in _sorted_gps(points):
        last_by_slot[local_slot_key(point.time, timezone, slot_seconds)] = point
    return [last_by_slot[key] for key in sorted(last_by_slot)]


def collapse_to_minute(points: list[GpsPoint], timezone: str) -> list[GpsPoint]:
    return collapse_to_slot(points, timezone, 60)


def local_slot_range(
    start: datetime,
    end: datetime,
    timezone: str,
    slot_seconds: int = GRID_SECONDS,
) -> list[datetime]:
    cursor = local_slot_key(start, timezone, slot_seconds)
    step = timedelta(seconds=slot_seconds)
    times: list[datetime] = []
    while cursor < end:
        times.append(cursor)
        cursor += step
    return times


def local_minute_range(start: datetime, end: datetime, timezone: str) -> list[datetime]:
    return local_slot_range(start, end, timezone, 60)


def slot_seconds_for(granularity: str) -> int:
    if granularity == "30s":
        return 30
    if granularity == "minute":
        return 60
    return GRID_SECONDS


def _spine_times(
    points: list[GpsPoint],
    granularity: str,
    timezone: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[datetime]:
    ordered = _sorted_gps(points)
    if granularity in {"30s", "minute"} and start is not None and end is not None:
        return local_slot_range(start, end, timezone, slot_seconds_for(granularity))
    if not ordered:
        return []
    if granularity == "30s":
        return [point.time for point in collapse_to_slot(ordered, timezone, 30)]
    if granularity == "minute":
        return [point.time for point in collapse_to_minute(ordered, timezone)]
    if granularity == "native":
        return [point.time for point in ordered]
    first = truncate_to_second(ordered[0].time)
    last = truncate_to_second(ordered[-1].time)
    if last < first:
        return [first]
    times: list[datetime] = []
    cursor = first
    while cursor <= last:
        times.append(cursor)
        cursor += timedelta(seconds=1)
    return times


def _empty_row(at: datetime) -> AlignedRow:
    return AlignedRow(
        time=at,
        latitude=None,
        longitude=None,
        speed_mph=None,
        address="",
        engine_raw=None,
        odometer_meters=None,
    )


def _sample_at(slot: datetime, slot_seconds: int) -> datetime:
    return slot + timedelta(seconds=slot_seconds) - timedelta(microseconds=1)


def _row_from_gps(
    slot: datetime,
    point: GpsPoint,
    engine_times: list[datetime],
    engine_values: list[str],
    odo_times: list[datetime],
    odo_values: list[float],
    slot_seconds: int,
) -> AlignedRow:
    at = _sample_at(slot, slot_seconds)
    return AlignedRow(
        time=slot,
        latitude=point.latitude,
        longitude=point.longitude,
        speed_mph=point.speed_mph,
        address=point.address,
        engine_raw=_asof(engine_times, engine_values, at),
        odometer_meters=_asof(odo_times, odo_values, at),
    )


def _copy_telemetry(dst: AlignedRow, src: AlignedRow) -> None:
    dst.latitude = src.latitude
    dst.longitude = src.longitude
    dst.speed_mph = src.speed_mph
    dst.address = src.address
    if dst.engine_raw is None:
        dst.engine_raw = src.engine_raw
    if dst.odometer_meters is None:
        dst.odometer_meters = src.odometer_meters


def _carry_empty_rows(rows: list[AlignedRow], carried: list[dict[str, str]]) -> None:
    last: AlignedRow | None = None
    for row in rows:
        if row.latitude is not None and row.longitude is not None:
            last = row
            continue
        if last is None:
            continue
        _copy_telemetry(row, last)
        carried.append({"minute": row.time.isoformat(), "source": "forward", "rule": FILL_RULE})
    first = next((row for row in rows if row.latitude is not None), None)
    if first is None:
        return
    for row in rows:
        if row.latitude is None or row.longitude is None:
            _copy_telemetry(row, first)
            carried.append({"minute": row.time.isoformat(), "source": "leading", "rule": FILL_RULE})
        else:
            break


def _carry_odometer(rows: list[AlignedRow]) -> None:
    first = next((row.odometer_meters for row in rows if row.odometer_meters is not None), None)
    last: float | None = None
    for row in rows:
        if row.odometer_meters is not None:
            last = row.odometer_meters
        elif last is not None:
            row.odometer_meters = last
    if first is None:
        return
    for row in rows:
        if row.odometer_meters is None:
            row.odometer_meters = first
        else:
            break


def align_slot_window(
    history: VehicleHistory,
    timezone: str,
    start: datetime,
    end: datetime,
    *,
    slot_seconds: int = GRID_SECONDS,
) -> tuple[list[AlignedRow], list[dict[str, Any]], int, list[dict[str, str]]]:
    """One output row per local slot in [start, end), with no empty cells.

    Same-slot GPS: last point by timestamp.
    Slots without a native GPS: last-known carry (lookback, then forward).
    Leading slots before the first in-window GPS: backward carry from that first point.
    Engine/OBD are as-of the end of each slot. First OBD is also carried backward.
    Coordinates are never interpolated.
    """
    expected = local_slot_range(start, end, timezone, slot_seconds)
    buckets: dict[datetime, list[GpsPoint]] = {slot: [] for slot in expected}
    out_of_range = 0
    ordered = _sorted_gps(history.gps)
    seed: GpsPoint | None = None
    for point in ordered:
        key = local_slot_key(point.time, timezone, slot_seconds)
        if key in buckets:
            buckets[key].append(point)
        elif start <= point.time < end:
            out_of_range += 1
        if point.time < start:
            seed = point

    engine_times = [event.time for event in sorted(history.engine_states, key=lambda e: e.time)]
    engine_values = [event.value for event in sorted(history.engine_states, key=lambda e: e.time)]
    odo_times = [event.time for event in sorted(history.obd_odometer, key=lambda e: e.time)]
    odo_values = [event.meters for event in sorted(history.obd_odometer, key=lambda e: e.time)]

    rows: list[AlignedRow] = []
    collapsed: list[dict[str, Any]] = []
    carried: list[dict[str, str]] = []
    last_gps = seed
    for slot in expected:
        points = buckets[slot]
        if points:
            chosen = points[-1]
            last_gps = chosen
            if len(points) > 1:
                collapsed.append(
                    {
                        "minute": slot.isoformat(),
                        "count": len(points),
                        "rule": SAME_SLOT_RULE,
                        "keptTime": chosen.time.isoformat(),
                        "discardedTimes": [point.time.isoformat() for point in points[:-1]],
                    }
                )
            rows.append(
                _row_from_gps(
                    slot,
                    chosen,
                    engine_times,
                    engine_values,
                    odo_times,
                    odo_values,
                    slot_seconds,
                )
            )
            continue
        if last_gps is not None:
            source = "lookback" if last_gps is seed and seed is not None else "forward"
            rows.append(
                _row_from_gps(
                    slot,
                    last_gps,
                    engine_times,
                    engine_values,
                    odo_times,
                    odo_values,
                    slot_seconds,
                )
            )
            carried.append({"minute": slot.isoformat(), "source": source, "rule": FILL_RULE})
            continue
        rows.append(_empty_row(slot))

    first_native = next((index for index, slot in enumerate(expected) if buckets[slot]), None)
    if first_native is not None:
        source_point = buckets[expected[first_native]][-1]
        for index in range(first_native):
            if rows[index].latitude is not None:
                continue
            rows[index] = _row_from_gps(
                expected[index],
                source_point,
                engine_times,
                engine_values,
                odo_times,
                odo_values,
                slot_seconds,
            )
            carried.append(
                {
                    "minute": expected[index].isoformat(),
                    "source": "leading",
                    "rule": FILL_RULE,
                }
            )

    _carry_empty_rows(rows, carried)
    _carry_odometer(rows)
    seen: set[str] = set()
    unique_carried: list[dict[str, str]] = []
    for item in carried:
        key = item["minute"]
        if key in seen:
            continue
        seen.add(key)
        unique_carried.append(item)
    return rows, collapsed, out_of_range, unique_carried


def align_minute_window(
    history: VehicleHistory,
    timezone: str,
    start: datetime,
    end: datetime,
) -> tuple[list[AlignedRow], list[dict[str, Any]], int, list[dict[str, str]]]:
    return align_slot_window(history, timezone, start, end, slot_seconds=60)


def align_history(
    history: VehicleHistory,
    granularity: str,
    timezone: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    fill_before_first: bool | None = None,
) -> list[AlignedRow]:
    del fill_before_first
    if granularity in {"30s", "minute"} and start is not None and end is not None:
        rows, _, _, _ = align_slot_window(
            history,
            timezone,
            start,
            end,
            slot_seconds=slot_seconds_for(granularity),
        )
        return rows

    gps = _sorted_gps(history.gps)
    engine_times = [event.time for event in sorted(history.engine_states, key=lambda e: e.time)]
    engine_values = [event.value for event in sorted(history.engine_states, key=lambda e: e.time)]
    odo_times = [event.time for event in sorted(history.obd_odometer, key=lambda e: e.time)]
    odo_values = [event.meters for event in sorted(history.obd_odometer, key=lambda e: e.time)]
    gps_times = [point.time for point in gps]

    rows: list[AlignedRow] = []
    for at in _spine_times(gps, granularity, timezone, start=start, end=end):
        gps_point = _asof(gps_times, gps, at)
        rows.append(
            AlignedRow(
                time=at,
                latitude=None if gps_point is None else gps_point.latitude,
                longitude=None if gps_point is None else gps_point.longitude,
                speed_mph=None if gps_point is None else gps_point.speed_mph,
                address="" if gps_point is None else gps_point.address,
                engine_raw=_asof(engine_times, engine_values, at),
                odometer_meters=_asof(odo_times, odo_values, at),
            )
        )
    return rows
