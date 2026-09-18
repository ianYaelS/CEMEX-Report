from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from constants import CODE_VERSION, FILL_RULE


@dataclass(slots=True)
class ReportParams:
    vehicle_id: str | None
    vehicle_name: str | None
    report_date: date
    start: datetime
    end: datetime
    timezone: str
    granularity: str
    csv_dialect: str
    api_base_url: str
    storage_prefix: str
    write_storage: bool = True
    include_csv: bool = False
    trigger_source: str | None = None
    correlation_id: str | None = None


@dataclass(slots=True)
class VehicleRef:
    id: str
    name: str


@dataclass(slots=True)
class GpsPoint:
    time: datetime
    latitude: float
    longitude: float
    speed_mph: float | None
    address: str
    is_ecu_speed: bool | None = None


@dataclass(slots=True)
class EngineEvent:
    time: datetime
    value: str


@dataclass(slots=True)
class OdometerEvent:
    time: datetime
    meters: float


@dataclass(slots=True)
class VehicleHistory:
    vehicle: VehicleRef
    gps: list[GpsPoint] = field(default_factory=list)
    engine_states: list[EngineEvent] = field(default_factory=list)
    obd_odometer: list[OdometerEvent] = field(default_factory=list)


@dataclass(slots=True)
class AlignedRow:
    time: datetime
    latitude: float | None
    longitude: float | None
    speed_mph: float | None
    address: str
    engine_raw: str | None
    odometer_meters: float | None


@dataclass(slots=True)
class ReportResult:
    vehicle_id: str
    vehicle_name: str
    report_date: str
    start: str
    end: str
    timezone: str
    granularity: str
    csv_dialect: str
    row_count: int
    storage_key: str
    summary_key: str
    filename: str
    csv_bytes: bytes
    stored: bool = False
    correlation_id: str | None = None
    validation_status: str = ""
    audit_key: str = ""
    gap_count: int = 0
    collapsed_count: int = 0
    carried_count: int = 0
    day_count: int = 1
    daily_row_counts: dict[str, int] = field(default_factory=dict)
    daily_files: list[str] = field(default_factory=list)
    engine_summary: dict[str, object] = field(default_factory=dict)

    def csv_text(self) -> str:
        return self.csv_bytes.decode("utf-8-sig")

    def _engine_note(self) -> str:
        check = str(self.engine_summary.get("idleCheck") or "")
        if check == "ok":
            return "La API envió Idle y el CSV tiene Ralentí. "
        if check == "api_has_no_idle":
            return "La API no envió Idle en este rango; no hay Ralentí que mostrar. "
        if check == "api_has_idle_csv_missing":
            return "La API envió Idle pero el CSV no tiene Ralentí. "
        return ""

    def summary(self, *, include_csv: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "statusCode": 200,
            "ok": True,
            "message": (
                f"{self.validation_status or 'VALID'}. "
                f"{self._engine_note()}"
                "Descarga el CSV en Storage "
                f"({self.storage_key if self.stored else self.filename})."
            ),
            "validationStatus": self.validation_status,
            "gapCount": self.gap_count,
            "collapsedCount": self.collapsed_count,
            "collapsedMinuteCount": self.collapsed_count,
            "carriedMinuteCount": self.carried_count,
            "fillRule": FILL_RULE,
            "codeVersion": CODE_VERSION,
            "dayCount": self.day_count,
            "dailyRowCounts": self.daily_row_counts,
            "dailyFiles": self.daily_files if self.stored else [],
            "audit_key": self.audit_key if self.stored else "",
            "vehicleId": self.vehicle_id,
            "vehicleName": self.vehicle_name,
            "reportDate": self.report_date,
            "period": {"start": self.start, "end": self.end},
            "timezone": self.timezone,
            "granularity": self.granularity,
            "csvDialect": self.csv_dialect,
            "rows_generated": self.row_count,
            "rowCount": self.row_count,
            "filename": self.filename,
            "stored": self.stored,
            "storage_key": self.storage_key if self.stored else "",
            "storageKey": self.storage_key if self.stored else "",
            "summary_key": self.summary_key if self.stored else "",
            "correlationId": self.correlation_id,
            "engine": self.engine_summary,
        }
        if include_csv:
            payload["csv"] = self.csv_text()
        return payload
