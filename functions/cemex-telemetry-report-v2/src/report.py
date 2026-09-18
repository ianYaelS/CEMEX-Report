from __future__ import annotations

import json

from datetime import timedelta

from align import align_history, align_slot_window, slot_seconds_for
from client import SamsaraClient
from constants import HISTORY_LOOKBACK_HOURS
from csv_writer import render_csv
from errors import ReportError
from minute_audit import INVALID, VALID, MinuteAudit, audit_slot_grid
from models import AlignedRow, ReportParams, ReportResult, VehicleHistory
from stats import fetch_history
from storage_io import (
    Storage,
    get_storage,
    in_function_runtime,
    persist_report_files,
    put_bytes,
    storage_object_key,
)
from timeutil import iter_local_day_windows, to_rfc3339
from transform import summarize_engine
from vehicles import resolve_vehicle


def _build_day_report(
    history: VehicleHistory,
    params: ReportParams,
    day_start,
    day_end,
) -> tuple[list[AlignedRow], MinuteAudit]:
    slot_seconds = slot_seconds_for(params.granularity)
    rows, collapsed, out_of_range, carried = align_slot_window(
        history,
        params.timezone,
        day_start,
        day_end,
        slot_seconds=slot_seconds,
    )
    audit = audit_slot_grid(
        rows,
        start=day_start,
        end=day_end,
        timezone=params.timezone,
        slot_seconds=slot_seconds,
        collapsed_minutes=collapsed,
        carried_minutes=carried,
        out_of_range_count=out_of_range,
    )
    return rows, audit


def _align_all_days(
    history: VehicleHistory,
    params: ReportParams,
    day_windows: list[tuple],
) -> tuple[list[list[AlignedRow]], list[tuple[str, MinuteAudit]]]:
    daily_rows: list[list[AlignedRow]] = []
    daily_audits: list[tuple[str, MinuteAudit]] = []
    for day_start, day_end in day_windows:
        rows, audit = _build_day_report(history, params, day_start, day_end)
        daily_rows.append(rows)
        daily_audits.append((day_start.date().isoformat(), audit))
    return daily_rows, daily_audits


def _range_audit_payload(
    daily_audits: list[tuple[str, MinuteAudit]],
    *,
    status: str,
    row_count: int,
) -> dict[str, object]:
    days = []
    for day, audit in daily_audits:
        days.append(
            {
                "date": day,
                "status": audit.status,
                "rowCount": audit.row_count,
                "nativeMinuteCount": audit.native_count,
                "carriedMinuteCount": audit.carried_count,
                "collapsedCount": len(audit.collapsed_minutes),
                "gapCount": audit.gap_count,
                "firstTimestamp": audit.first_timestamp,
                "lastTimestamp": audit.last_timestamp,
            }
        )
    return {
        "status": status,
        "dayCount": len(daily_audits),
        "rowCount": row_count,
        "slotSeconds": daily_audits[0][1].slot_seconds if daily_audits else 30,
        "expectedSlots": sum(audit.expected_minutes for _, audit in daily_audits),
        "expectedMinutes": sum(audit.expected_minutes for _, audit in daily_audits),
        "dailyRowCounts": {day: audit.row_count for day, audit in daily_audits},
        "dailyStatus": {day: audit.status for day, audit in daily_audits},
        "gapCount": sum(audit.gap_count for _, audit in daily_audits),
        "carriedSlotCount": sum(audit.carried_count for _, audit in daily_audits),
        "carriedMinuteCount": sum(audit.carried_count for _, audit in daily_audits),
        "collapsedCount": sum(len(audit.collapsed_minutes) for _, audit in daily_audits),
        "fillRule": "last_known_carry",
        "sameSlotRule": "last_gps_by_timestamp",
        "sameMinuteRule": "last_gps_by_timestamp",
        "days": days,
        "engine": None,
    }


def generate_report(
    params: ReportParams,
    token: str,
    *,
    storage: Storage | None = None,
    client: SamsaraClient | None = None,
) -> ReportResult:
    owns_client = client is None
    http = client or SamsaraClient(params.api_base_url, token)
    try:
        vehicle = resolve_vehicle(
            http,
            vehicle_id=params.vehicle_id,
            vehicle_name=params.vehicle_name,
            trigger_source=params.trigger_source,
        )
        fetch_start = params.start - timedelta(hours=HISTORY_LOOKBACK_HOURS)
        history = fetch_history(http, vehicle, fetch_start, params.end)
        vehicle = history.vehicle
        tracking = params.csv_dialect == "tracking"
        cemex_grid = (not tracking) and params.granularity in {"30s", "minute"}
        slot_seconds = slot_seconds_for(params.granularity)
        rows_per_day = 24 * 60 * 60 // slot_seconds
        day_windows = (
            iter_local_day_windows(params.start, params.end, params.timezone)
            if cemex_grid
            else []
        )
        daily_rows: list[list[AlignedRow]] = []
        daily_audits: list[tuple[str, MinuteAudit]] = []
        collapsed_total = 0
        carried_total = 0
        status = VALID
        gap_total = 0
        daily_row_counts: dict[str, int] = {}

        if cemex_grid:
            daily_rows, daily_audits = _align_all_days(history, params, day_windows)
            if any(audit.gap_count for _, audit in daily_audits):
                history = fetch_history(http, vehicle, fetch_start, params.end)
                daily_rows, daily_audits = _align_all_days(history, params, day_windows)
            rows = [row for block in daily_rows for row in block]
            status = (
                INVALID
                if any(audit.status == INVALID for _, audit in daily_audits)
                else VALID
            )
            gap_total = sum(audit.gap_count for _, audit in daily_audits)
            collapsed_total = sum(
                len(audit.collapsed_minutes) for _, audit in daily_audits
            )
            carried_total = sum(audit.carried_count for _, audit in daily_audits)
            daily_row_counts = {day: audit.row_count for day, audit in daily_audits}
            expected_total = len(daily_audits) * rows_per_day
            if any(count != rows_per_day for count in daily_row_counts.values()):
                raise ReportError(
                    f"each daily grid must have {rows_per_day} rows; got {daily_row_counts}"
                )
            if len(rows) != expected_total:
                raise ReportError(
                    f"rowCount must be {expected_total} "
                    f"({len(daily_audits)} days × {rows_per_day}); got {len(rows)}"
                )
        else:
            rows = align_history(
                history,
                "native" if tracking else params.granularity,
                params.timezone,
                start=None if tracking else params.start,
                end=None if tracking else params.end,
            )
        engine = summarize_engine(history, rows, params.csv_dialect)
        if engine["idleCheck"] == "api_has_idle_csv_missing":
            status = INVALID

        if rows:
            print(
                json.dumps(
                    {
                        "event": "coverage",
                        "firstTimestamp": rows[0].time.isoformat(),
                        "lastTimestamp": rows[-1].time.isoformat(),
                        "rowCount": len(rows),
                        "dayCount": len(daily_audits) or 1,
                        "dailyRowCounts": daily_row_counts,
                        "validationStatus": status,
                        "gapCount": gap_total,
                        "collapsedMinuteCount": collapsed_total,
                        "carriedMinuteCount": carried_total,
                        "slotSeconds": slot_seconds,
                        "fillRule": "last_known_carry",
                        "ecuSpeedPoints": sum(
                            1 for point in history.gps if point.is_ecu_speed
                        ),
                        "speedSource": "gps.speedMilesPerHour * 1.609344",
                        "odometerSource": "obdOdometerMeters / 1000",
                        "sameMinuteRule": "last_gps_by_timestamp",
                        "engine": engine,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
                flush=True,
            )

        csv_bytes = render_csv(rows, params.timezone, params.csv_dialect)
        unit_name = vehicle.name or params.vehicle_name or vehicle.id
        should_store = params.write_storage or (storage is None and in_function_runtime())
        backend = storage
        if should_store:
            backend = storage or get_storage(require_persistent=in_function_runtime())

        daily_files: list[str] = []
        first_audit_key = ""
        primary_key = storage_object_key(
            params.storage_prefix,
            unit_name,
            params.start,
            params.end,
            params.granularity,
            params.timezone,
            vehicle_id=vehicle.id,
        )
        if should_store and backend is not None:
            persist_report_files(backend, csv_key=primary_key, csv_bytes=csv_bytes)
            daily_files = [primary_key]
            if cemex_grid and daily_audits:
                first_audit_key = (
                    primary_key[:-4] + "_auditoria.json"
                    if primary_key.endswith(".csv")
                    else f"{primary_key}_auditoria.json"
                )
                audit_payload = (
                    daily_audits[0][1].to_dict()
                    if len(daily_audits) == 1
                    else _range_audit_payload(
                        daily_audits, status=status, row_count=len(rows)
                    )
                )
                audit_payload["engine"] = engine
                put_bytes(
                    backend,
                    first_audit_key,
                    json.dumps(audit_payload, ensure_ascii=False, indent=2).encode(
                        "utf-8"
                    ),
                )

        filename = primary_key.rsplit("/", 1)[-1]
        return ReportResult(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle.name,
            license_plate=vehicle.license_plate,
            report_date=params.report_date.isoformat(),
            start=to_rfc3339(params.start),
            end=to_rfc3339(params.end),
            timezone=params.timezone,
            granularity=params.granularity,
            csv_dialect=params.csv_dialect,
            row_count=len(rows),
            storage_key=primary_key,
            summary_key=first_audit_key,
            filename=filename,
            csv_bytes=csv_bytes,
            stored=bool(should_store and backend is not None),
            correlation_id=params.correlation_id,
            validation_status=status,
            audit_key=first_audit_key,
            gap_count=gap_total,
            collapsed_count=collapsed_total,
            carried_count=carried_total,
            day_count=len(daily_audits) or 1,
            daily_row_counts=daily_row_counts,
            daily_files=daily_files,
            engine_summary=engine,
        )
    finally:
        if owns_client:
            http.close()
