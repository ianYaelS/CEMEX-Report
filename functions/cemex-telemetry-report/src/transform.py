from __future__ import annotations

from collections import Counter

from constants import (
    COORD_DECIMALS,
    ENGINE_IDLE_EN,
    ENGINE_IDLE_ES,
    ENGINE_OFF_EN,
    ENGINE_OFF_ES,
    ENGINE_ON_EN,
    ENGINE_ON_ES,
    METERS_PER_KM,
    MPH_TO_KMH,
    ODOMETER_DECIMALS,
    SPEED_DECIMALS,
)
from models import AlignedRow, VehicleHistory
from timeutil import format_local_timestamp, format_tracking_timestamp


def mph_to_kmh(mph: float) -> float:
    return mph * MPH_TO_KMH


def meters_to_km(meters: float) -> float:
    return meters / METERS_PER_KM


def format_number(value: float, max_decimals: int = 6, *, decimals: int | None = None) -> str:
    if decimals is not None:
        return f"{value:.{decimals}f}"
    text = f"{value:.{max_decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _normalize_engine(raw: str | None) -> str:
    return "" if raw is None else raw.strip().lower()


def is_idle_raw(raw: str | None) -> bool:
    normalized = _normalize_engine(raw)
    return normalized in {"idle", "on (idle)", "idling"} or (
        "idle" in normalized and normalized != ""
    )


def raw_engine_bucket(raw: str | None) -> str:
    normalized = _normalize_engine(raw)
    if normalized in {"off", "none", ""}:
        return "Off"
    if is_idle_raw(raw):
        return "Idle"
    if normalized == "on" or normalized.startswith("on"):
        return "On"
    return raw.strip() if raw and raw.strip() else "Off"


def summarize_engine(history: VehicleHistory, rows: list[AlignedRow], dialect: str) -> dict[str, object]:
    api_counts = Counter(raw_engine_bucket(event.value) for event in history.engine_states)
    csv_counts = Counter(map_engine_state(row.engine_raw, dialect) for row in rows)
    idle_events = [event for event in history.engine_states if is_idle_raw(event.value)]
    ralenti_label = ENGINE_IDLE_ES if dialect == "es" else ENGINE_IDLE_EN
    idle_in_api = bool(idle_events)
    idle_in_csv = csv_counts.get(ralenti_label, 0) > 0 or csv_counts.get("On (Idle)", 0) > 0
    if idle_in_api and not idle_in_csv:
        idle_check = "api_has_idle_csv_missing"
    elif idle_in_api:
        idle_check = "ok"
    else:
        idle_check = "api_has_no_idle"
    return {
        "apiCounts": dict(api_counts),
        "csvCounts": dict(csv_counts),
        "idleEvents": len(idle_events),
        "idleInApi": idle_in_api,
        "idleInCsv": idle_in_csv,
        "idleCheck": idle_check,
        "firstIdleAt": idle_events[0].time.isoformat() if idle_events else "",
        "lastIdleAt": idle_events[-1].time.isoformat() if idle_events else "",
        "uniqueApiValues": sorted({event.value for event in history.engine_states if event.value}),
    }


def map_engine_state(raw: str | None, dialect: str = "es") -> str:
    if dialect == "tracking":
        return map_engine_tracking(raw)
    on_label = ENGINE_ON_ES if dialect == "es" else ENGINE_ON_EN
    off_label = ENGINE_OFF_ES if dialect == "es" else ENGINE_OFF_EN
    idle_label = ENGINE_IDLE_ES if dialect == "es" else ENGINE_IDLE_EN
    normalized = "" if raw is None else raw.strip().lower()
    if normalized in {"off", "none", ""}:
        return off_label
    if normalized in {"idle", "on (idle)"} or "idle" in normalized:
        return idle_label
    if normalized == "on" or normalized.startswith("on"):
        return on_label
    return off_label


def map_engine_tracking(raw: str | None) -> str:
    normalized = "" if raw is None else raw.strip().lower()
    if normalized in {"off", "none", ""}:
        return "Off"
    if normalized in {"idle", "on (idle)"}:
        return "On (Idle)"
    if normalized in {"on (driving)"}:
        return "On (Driving)"
    if normalized == "on" or normalized.startswith("on"):
        return "On (Driving)"
    return "Off"


def row_to_cells(row: AlignedRow, timezone: str, dialect: str) -> list[str]:
    tracking = dialect == "tracking"
    speed = (
        ""
        if row.speed_mph is None
        else format_number(
            mph_to_kmh(row.speed_mph),
            decimals=None if tracking else SPEED_DECIMALS,
        )
    )
    latitude = (
        ""
        if row.latitude is None
        else format_number(
            row.latitude,
            decimals=None if tracking else COORD_DECIMALS,
        )
    )
    longitude = (
        ""
        if row.longitude is None
        else format_number(
            row.longitude,
            decimals=None if tracking else COORD_DECIMALS,
        )
    )
    odometer = (
        ""
        if row.odometer_meters is None
        else format_number(
            meters_to_km(row.odometer_meters),
            decimals=None if tracking else ODOMETER_DECIMALS,
        )
    )
    stamp = (
        format_tracking_timestamp(row.time, timezone)
        if tracking
        else format_local_timestamp(row.time, timezone)
    )
    engine = (
        ""
        if row.latitude is None and row.longitude is None and dialect != "tracking"
        else map_engine_state(row.engine_raw, dialect)
    )
    return [
        stamp,
        engine,
        speed,
        latitude,
        longitude,
        odometer,
        row.address or "",
    ]
