from __future__ import annotations

import json
import traceback
from typing import Any

from errors import ReportError
from params import parse_params
from report import generate_report
from secrets_io import load_secrets, resolve_token, secrets_debug


def _log(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def main(event: dict[str, Any] | None, context: Any = None) -> dict[str, Any]:
    event = event or {}
    correlation_id = str(event.get("SamsaraFunctionCorrelationId") or "")
    trigger = str(event.get("SamsaraFunctionTriggerSource") or "")
    _log(
        {
            "event": "start",
            "correlationId": correlation_id,
            "triggerSource": trigger,
        }
    )
    try:
        params = parse_params(event)
        _log(
            {
                "event": "params",
                "correlationId": correlation_id,
                "vehicleName": params.vehicle_name,
                "vehicleId": params.vehicle_id,
                "start": params.start.isoformat(),
                "end": params.end.isoformat(),
                "timezone": params.timezone,
                "granularity": params.granularity,
            }
        )
        secrets = load_secrets()
        _log(
            {
                "event": "secrets",
                "correlationId": correlation_id,
                **secrets_debug(secrets),
            }
        )
        token = resolve_token(secrets, event=event)
        result = generate_report(params, token)
        summary = result.summary(include_csv=params.include_csv)
        _log(
            {
                "event": "finish",
                "ok": True,
                "correlationId": correlation_id or result.correlation_id,
                "filename": result.filename,
                "rows_generated": result.row_count,
                "validationStatus": result.validation_status,
                "gapCount": result.gap_count,
                "stored": result.stored,
                "storageKey": result.storage_key if result.stored else "",
                "period": summary["period"],
            }
        )
        return summary
    except Exception as exc:
        _log(
            {
                "event": "finish",
                "ok": False,
                "correlationId": correlation_id,
                "errorType": type(exc).__name__,
                "error": str(exc),
            }
        )
        if isinstance(exc, ReportError):
            raise
        traceback.print_exc()
        raise
