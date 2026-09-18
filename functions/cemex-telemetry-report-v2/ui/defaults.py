from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PARAMS_PATH = ROOT / "config" / "params.json"


def _text(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_day(value: str, fallback: date) -> date:
    text = (value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return fallback


def load_function_defaults(path: Path | None = None) -> dict[str, Any]:
    """Same keys as Function Event parameters; token never comes from the JSON file."""
    yesterday = date.today() - timedelta(days=1)
    raw: dict[str, Any] = {}
    source = path or PARAMS_PATH
    if source.exists():
        loaded = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw = loaded
    start = _parse_day(_text(raw, "start_time", "startTime"), yesterday)
    end = _parse_day(_text(raw, "end_time", "endTime"), start)
    if end < start:
        end = start
    return {
        "vehicle_id": _text(raw, "vehicle_id", "vehicleId") or os.environ.get("vehicle_id", "").strip(),
        "start_time": start,
        "end_time": end,
        "timezone": _text(raw, "timezone") or "America/Mexico_City",
        "granularity": _text(raw, "granularity") or "30s",
        "csv_dialect": _text(raw, "csv_dialect", "csvDialect") or "es",
        "params_path": str(source),
    }


def resolve_api_key(*, secrets: Any | None = None) -> str:
    for key in ("api_key", "apiKey", "SAMSARA_API_TOKEN", "SAMSARA_KEY"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    if secrets is None:
        return ""
    try:
        for key in ("api_key", "apiKey", "SAMSARA_API_TOKEN"):
            value = str(secrets.get(key, "") or "").strip()
            if value:
                return value
    except Exception:
        return ""
    return ""
