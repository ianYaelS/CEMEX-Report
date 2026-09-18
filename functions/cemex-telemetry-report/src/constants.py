from __future__ import annotations

# /fleet/vehicles/stats/history accepts at most 3 types. Never include gpsOdometerMeters.
HISTORY_TYPES = "gps,engineStates,obdOdometerMeters"

MPH_TO_KMH = 1.609344
METERS_PER_KM = 1000.0

DEFAULT_TIMEZONE = "America/Mexico_City"
DEFAULT_GRANULARITY = "minute"
DEFAULT_CSV_DIALECT = "es"
DEFAULT_API_BASE_URL = "https://api.samsara.com"
DEFAULT_STORAGE_PREFIX = "CEMEX_Reportes"
MAX_RANGE_DAYS = 7
HISTORY_LOOKBACK_HOURS = 24
FILL_RULE = "last_known_carry"
CODE_VERSION = "cemex-idle-audit-2026-09-16"
SPEED_DECIMALS = 2
ODOMETER_DECIMALS = 2
COORD_DECIMALS = 6
ES_CSV_DELIMITER = ";"
EN_CSV_DELIMITER = ","

GRANULARITIES = frozenset({"minute", "native", "second"})
CSV_DIALECTS = frozenset({"es", "en", "tracking"})
TOKEN_SECRET_KEYS = (
    "SAMSARA_API_TOKEN",
    "SAMSARA_KEY",
    "api_key",
    "apiKey",
    "api_token",
    "apiToken",
)
EVENT_TOKEN_KEYS = TOKEN_SECRET_KEYS

CSV_HEADERS_ES: tuple[str, ...] = (
    "Fecha y hora",
    "Estado de motor (Encendido, Apagado, Ralentí)",
    "Velocidad de vehiculo en Km/hr",
    "Latitud GPS",
    "Longitud GPS",
    "Odómetro en Km",
    "Nombre de dirección de posición basado en GPS",
)

CSV_HEADERS_EN: tuple[str, ...] = (
    "Date and time",
    "Engine status (On, Off, Idle)",
    "Vehicle speed in Km/hr",
    "GPS Latitude",
    "GPS Longitude",
    "Odometer in Km",
    "GPS Position Address",
)

CSV_HEADERS_TRACKING: tuple[str, ...] = (
    "Tracking Point Date",
    "Engine Status",
    "ECU Speed (KPH)",
    "GPS Latitude",
    "GPS Longitude",
    "ECU Odometer (KM)",
    "GPS Position Address",
)

ENGINE_ON_ES = "Encendido"
ENGINE_OFF_ES = "Apagado"
ENGINE_IDLE_ES = "Ralentí"
ENGINE_ON_EN = "On"
ENGINE_OFF_EN = "Off"
ENGINE_IDLE_EN = "Idle"

UTF8_BOM = b"\xef\xbb\xbf"
