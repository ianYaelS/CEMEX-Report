from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from align import local_slot_range
from constants import FILL_RULE, GRID_SECONDS
from models import AlignedRow
from timeutil import format_local_timestamp


VALID = "VALID"
INVALID = "INVALIDO/PENDIENTE"
SAME_SLOT_RULE = "last_gps_by_timestamp"


def _compress_slots(stamps: list[str], slot_seconds: int) -> list[dict[str, Any]]:
    if not stamps:
        return []
    parsed = [datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S") for stamp in stamps]
    step = timedelta(seconds=slot_seconds)
    ranges: list[dict[str, Any]] = []
    start = parsed[0]
    prev = parsed[0]
    for current in parsed[1:]:
        if current == prev + step:
            prev = current
            continue
        ranges.append(
            {
                "from": start.strftime("%Y-%m-%d %H:%M:%S"),
                "to": prev.strftime("%Y-%m-%d %H:%M:%S"),
                "slots": int((prev - start).total_seconds() // slot_seconds) + 1,
            }
        )
        start = current
        prev = current
    ranges.append(
        {
            "from": start.strftime("%Y-%m-%d %H:%M:%S"),
            "to": prev.strftime("%Y-%m-%d %H:%M:%S"),
            "slots": int((prev - start).total_seconds() // slot_seconds) + 1,
        }
    )
    return ranges


@dataclass
class MinuteAudit:
    status: str
    expected_minutes: int
    row_count: int
    unique_timestamps: int
    first_timestamp: str
    last_timestamp: str
    same_minute_rule: str = SAME_SLOT_RULE
    fill_rule: str = FILL_RULE
    slot_seconds: int = GRID_SECONDS
    gaps: list[str] = field(default_factory=list)
    collapsed_minutes: list[dict[str, Any]] = field(default_factory=list)
    carried_local: list[str] = field(default_factory=list)
    out_of_range_count: int = 0
    grid: dict[str, bool] = field(default_factory=dict)

    @property
    def gap_count(self) -> int:
        return len(self.gaps)

    @property
    def carried_count(self) -> int:
        return len(self.carried_local)

    @property
    def native_count(self) -> int:
        return max(self.row_count - self.carried_count - self.gap_count, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "slotSeconds": self.slot_seconds,
            "expectedSlots": self.expected_minutes,
            "expectedMinutes": self.expected_minutes,
            "rowCount": self.row_count,
            "uniqueTimestamps": self.unique_timestamps,
            "firstTimestamp": self.first_timestamp,
            "lastTimestamp": self.last_timestamp,
            "sameSlotRule": self.same_minute_rule,
            "sameMinuteRule": self.same_minute_rule,
            "fillRule": self.fill_rule,
            "nativeSlotCount": self.native_count,
            "nativeMinuteCount": self.native_count,
            "carriedSlotCount": self.carried_count,
            "carriedMinuteCount": self.carried_count,
            "carriedRanges": _compress_slots(self.carried_local, self.slot_seconds),
            "gapCount": self.gap_count,
            "gaps": self.gaps,
            "collapsedCount": len(self.collapsed_minutes),
            "collapsedMinutes": self.collapsed_minutes,
            "outOfRangeCount": self.out_of_range_count,
            "gridChecks": self.grid,
        }


def audit_slot_grid(
    rows: list[AlignedRow],
    *,
    start: datetime,
    end: datetime,
    timezone: str,
    slot_seconds: int = GRID_SECONDS,
    collapsed_minutes: list[dict[str, Any]] | None = None,
    carried_minutes: list[dict[str, str]] | None = None,
    out_of_range_count: int = 0,
) -> MinuteAudit:
    expected = local_slot_range(start, end, timezone, slot_seconds)
    times = [row.time for row in rows]
    unique = {format_local_timestamp(row.time, timezone) for row in rows}
    first = format_local_timestamp(rows[0].time, timezone) if rows else ""
    last = format_local_timestamp(rows[-1].time, timezone) if rows else ""
    expected_first = format_local_timestamp(expected[0], timezone) if expected else ""
    expected_last = format_local_timestamp(expected[-1], timezone) if expected else ""

    gaps = [
        format_local_timestamp(row.time, timezone)
        for row in rows
        if row.latitude is None and row.longitude is None
    ]
    carried_local = sorted(
        {
            format_local_timestamp(datetime.fromisoformat(item["minute"]), timezone)
            for item in (carried_minutes or [])
        }
    )

    in_range = all(start <= row.time < end for row in rows)
    sequential = times == expected
    no_empty = not gaps
    grid = {
        "rowCountEqualsExpected": len(rows) == len(expected),
        "uniqueEqualsExpected": len(unique) == len(expected),
        "firstIsStart": first == expected_first,
        "lastIsEndSlot": last == expected_last,
        "lastIs2359": last == expected_last,
        "noMissingOutputSlot": sequential,
        "noMissingOutputMinute": sequential,
        "noDuplicateOutputSlot": len(times) == len(set(times)),
        "noDuplicateOutputMinute": len(times) == len(set(times)),
        "allTimestampsInRange": in_range,
        "noEmptyCells": no_empty,
    }
    fatal_grid = not all(grid.values())
    status = INVALID if gaps or fatal_grid or out_of_range_count else VALID
    return MinuteAudit(
        status=status,
        expected_minutes=len(expected),
        row_count=len(rows),
        unique_timestamps=len(unique),
        first_timestamp=first,
        last_timestamp=last,
        slot_seconds=slot_seconds,
        gaps=gaps,
        collapsed_minutes=collapsed_minutes or [],
        carried_local=carried_local,
        out_of_range_count=out_of_range_count,
        grid=grid,
    )


def audit_minute_grid(
    rows: list[AlignedRow],
    *,
    start: datetime,
    end: datetime,
    timezone: str,
    collapsed_minutes: list[dict[str, Any]] | None = None,
    carried_minutes: list[dict[str, str]] | None = None,
    out_of_range_count: int = 0,
) -> MinuteAudit:
    return audit_slot_grid(
        rows,
        start=start,
        end=end,
        timezone=timezone,
        slot_seconds=60,
        collapsed_minutes=collapsed_minutes,
        carried_minutes=carried_minutes,
        out_of_range_count=out_of_range_count,
    )
