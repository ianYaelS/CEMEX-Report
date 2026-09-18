from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from errors import ConfigError


def load_zoneinfo(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ConfigError(f"unknown timezone: {name}") from exc


def parse_report_date(value: str, *, field: str = "report_date") -> date:
    text = (value or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ConfigError(f"invalid {field}, expected YYYY-MM-DD: {value!r}") from exc


def yesterday_in_timezone(tz_name: str, now: datetime | None = None) -> date:
    tz = load_zoneinfo(tz_name)
    current = now.astimezone(tz) if now is not None else datetime.now(tz)
    return (current.date() - timedelta(days=1))


def iter_local_day_windows(
    start: datetime,
    end: datetime,
    tz_name: str,
) -> list[tuple[datetime, datetime]]:
    tz = load_zoneinfo(tz_name)
    first = start.astimezone(tz).date()
    last = (end.astimezone(tz) - timedelta(microseconds=1)).date()
    windows: list[tuple[datetime, datetime]] = []
    day = first
    while day <= last:
        windows.append(local_day_bounds(day, tz_name))
        day += timedelta(days=1)
    return windows


def local_day_bounds(report_date: date, tz_name: str) -> tuple[datetime, datetime]:
    tz = load_zoneinfo(tz_name)
    start = datetime(
        report_date.year,
        report_date.month,
        report_date.day,
        tzinfo=tz,
    )
    end = start + timedelta(days=1)
    return start, end


def parse_bound(value: str, tz_name: str, *, field: str, is_end: bool) -> datetime:
    text = (value or "").strip()
    if len(text) == 10 and text[4:5] == "-" and text[7:8] == "-":
        day = parse_report_date(text, field=field)
        start, end = local_day_bounds(day, tz_name)
        return end if is_end else start
    try:
        return parse_api_time(text)
    except ValueError as exc:
        raise ConfigError(
            f"invalid {field}, expected YYYY-MM-DD or RFC3339: {value!r}"
        ) from exc


def to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_api_time(value: str) -> datetime:
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_local_timestamp(dt: datetime, tz_name: str) -> str:
    tz = load_zoneinfo(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")


def format_tracking_timestamp(dt: datetime, tz_name: str) -> str:
    tz = load_zoneinfo(tz_name)
    local = dt.astimezone(tz)
    offset = local.utcoffset() or timedelta(0)
    abbrev = "CST" if offset == timedelta(hours=-6) else (local.tzname() or "CST")
    return f"{local.strftime('%Y-%m-%d %H:%M:%S')} {abbrev}"


def truncate_to_second(dt: datetime) -> datetime:
    return dt.replace(microsecond=0)


def local_slot_key(dt: datetime, tz_name: str, slot_seconds: int = 30) -> datetime:
    tz = load_zoneinfo(tz_name)
    local = dt.astimezone(tz)
    if slot_seconds <= 0 or 60 % slot_seconds:
        raise ValueError(f"slot_seconds must divide 60: {slot_seconds}")
    second = (local.second // slot_seconds) * slot_seconds
    return local.replace(second=second, microsecond=0)


def local_minute_key(dt: datetime, tz_name: str) -> datetime:
    return local_slot_key(dt, tz_name, 60)
