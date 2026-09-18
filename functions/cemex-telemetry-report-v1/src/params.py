from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from constants import (
    CSV_DIALECTS,
    DEFAULT_API_BASE_URL,
    DEFAULT_CSV_DIALECT,
    DEFAULT_GRANULARITY,
    DEFAULT_STORAGE_PREFIX,
    DEFAULT_TIMEZONE,
    GRANULARITIES,
    MAX_RANGE_DAYS,
)
from errors import ConfigError
from models import ReportParams
from timeutil import load_zoneinfo, local_day_bounds, parse_bound, parse_report_date, yesterday_in_timezone


def _first_text(event: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key not in event:
            continue
        value = event[key]
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "si", "sí"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ConfigError(f"invalid boolean {value!r}; expected true or false")


def _require_https(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigError(f"api_base_url must be https: {url!r}")
    return url.rstrip("/")


def _resolve_window(
    event: Mapping[str, Any],
    timezone: str,
    now: datetime | None,
) -> tuple[datetime, datetime]:
    start_raw = _first_text(
        event, "start_time", "startTime", "start_date", "startDate"
    )
    end_raw = _first_text(event, "end_time", "endTime", "end_date", "endDate")
    report_raw = _first_text(event, "report_date", "reportDate")

    if start_raw and end_raw:
        start = parse_bound(start_raw, timezone, field="start_time", is_end=False)
        end = parse_bound(end_raw, timezone, field="end_time", is_end=True)
    elif start_raw:
        start = parse_bound(start_raw, timezone, field="start_time", is_end=False)
        end = start + timedelta(days=1)
    elif report_raw:
        start, end = local_day_bounds(parse_report_date(report_raw), timezone)
    else:
        start, end = local_day_bounds(yesterday_in_timezone(timezone, now=now), timezone)

    if end <= start:
        raise ConfigError("end_time must be after start_time")
    span = end - start
    if span > timedelta(days=MAX_RANGE_DAYS):
        raise ConfigError(
            f"search range exceeds {MAX_RANGE_DAYS} days (Functions timeout ~15 min)"
        )
    return start, end


def parse_params(
    event: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> ReportParams:
    timezone = _first_text(event, "timezone") or DEFAULT_TIMEZONE
    tz = load_zoneinfo(timezone)
    start, end = _resolve_window(event, timezone, now)

    granularity = (_first_text(event, "granularity") or DEFAULT_GRANULARITY).lower()
    if granularity not in GRANULARITIES:
        raise ConfigError(
            f"unknown granularity {granularity!r}; expected one of {sorted(GRANULARITIES)}"
        )

    csv_dialect = (_first_text(event, "csv_dialect", "csvDialect") or DEFAULT_CSV_DIALECT).lower()
    if csv_dialect not in CSV_DIALECTS:
        raise ConfigError(
            f"unknown csv_dialect {csv_dialect!r}; expected one of {sorted(CSV_DIALECTS)}"
        )

    api_base_url = _require_https(
        _first_text(event, "api_base_url", "apiBaseUrl") or DEFAULT_API_BASE_URL
    )
    storage_prefix = (
        _first_text(
            event,
            "storage_prefix",
            "storagePrefix",
            "output_key_prefix",
            "outputKeyPrefix",
        )
        or DEFAULT_STORAGE_PREFIX
    )

    vehicle_id = _first_text(event, "vehicle_id", "vehicleId", "assetId")
    vehicle_name = _first_text(event, "vehicle_name", "vehicleName")
    if vehicle_id is None and vehicle_name is None:
        raise ConfigError("vehicle_id is required")

    write_storage = _as_bool(
        _first_text(event, "write_storage", "writeStorage"),
        default=True,
    )
    include_csv = _as_bool(
        _first_text(event, "include_csv", "includeCsv"),
        default=False,
    )

    return ReportParams(
        vehicle_id=vehicle_id,
        vehicle_name=vehicle_name,
        report_date=start.astimezone(tz).date(),
        start=start,
        end=end,
        timezone=timezone,
        granularity=granularity,
        csv_dialect=csv_dialect,
        api_base_url=api_base_url,
        storage_prefix=storage_prefix,
        write_storage=write_storage,
        include_csv=include_csv,
        trigger_source=_first_text(event, "SamsaraFunctionTriggerSource"),
        correlation_id=_first_text(event, "SamsaraFunctionCorrelationId"),
    )
