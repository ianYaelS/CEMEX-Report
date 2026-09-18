from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "functions" / "cemex-telemetry-report" / "src"
sys.path.insert(0, str(SRC))

from constants import (  # noqa: E402
    DEFAULT_API_BASE_URL,
    DEFAULT_CSV_DIALECT,
    DEFAULT_GRANULARITY,
    DEFAULT_TIMEZONE,
)
from params import parse_params  # noqa: E402
from report import generate_report  # noqa: E402
from secrets_io import resolve_token  # noqa: E402
from storage_io import LocalStorage  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the CEMEX daily telemetry CSV (same logic as the Samsara Function)."
    )
    vehicle = parser.add_mutually_exclusive_group(required=True)
    vehicle.add_argument("--vehicle-id", dest="vehicle_id", help="Samsara vehicle id")
    vehicle.add_argument("--vehicle-name", dest="vehicle_name", help="Fleet name, e.g. FAV76")
    parser.add_argument("--date", dest="report_date", help="Single local day YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--start-time", dest="start_time", help="Range start: YYYY-MM-DD or RFC3339")
    parser.add_argument("--end-time", dest="end_time", help="Range end: YYYY-MM-DD or RFC3339")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--granularity", default=DEFAULT_GRANULARITY, choices=("minute", "native", "second"))
    parser.add_argument("--csv-dialect", dest="csv_dialect", default=DEFAULT_CSV_DIALECT, choices=("es", "en"))
    parser.add_argument("--api-base-url", dest="api_base_url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--storage-prefix", dest="storage_prefix", default="CEMEX_Reportes")
    parser.add_argument("--token", help="Samsara API token (otherwise SAMSARA_API_TOKEN / SAMSARA_KEY)")
    parser.add_argument("--output", required=True, help="Local CSV path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    event = {
        "vehicle_id": args.vehicle_id,
        "vehicle_name": args.vehicle_name,
        "report_date": args.report_date,
        "start_time": args.start_time,
        "end_time": args.end_time,
        "timezone": args.timezone,
        "granularity": args.granularity,
        "csv_dialect": args.csv_dialect,
        "api_base_url": args.api_base_url,
        "storage_prefix": args.storage_prefix,
    }
    params = parse_params({key: value for key, value in event.items() if value})
    token = args.token or resolve_token()
    storage = LocalStorage()
    result = generate_report(params, token, storage=storage)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.csv_bytes)
    print(
        f"wrote {output} ({result.row_count} rows) storage_key={result.storage_key}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
