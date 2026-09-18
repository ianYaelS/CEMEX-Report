from __future__ import annotations


class ReportError(Exception):
    """Base error for the CEMEX telemetry report."""


class ConfigError(ReportError):
    """Invalid or missing event/CLI parameters."""


class VehicleNotFoundError(ReportError):
    """Vehicle id or name did not resolve in the fleet."""


class StatsEmptyError(ReportError):
    """History returned no GPS points for the requested day."""


class StorageError(ReportError):
    """Function Storage is required but unavailable."""


class ApiError(ReportError):
    """Samsara HTTP API failure."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
