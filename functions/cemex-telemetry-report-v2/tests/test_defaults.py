from __future__ import annotations

from datetime import date
from pathlib import Path

from defaults import load_function_defaults


def test_load_function_defaults_reads_event_keys(tmp_path: Path) -> None:
    path = tmp_path / "params.json"
    path.write_text(
        '{"vehicle_id":"281475002878096","start_time":"2026-08-31","end_time":"2026-08-31"}',
        encoding="utf-8",
    )
    defaults = load_function_defaults(path)
    assert defaults["vehicle_id"] == "281475002878096"
    assert defaults["start_time"] == date(2026, 8, 31)
    assert defaults["end_time"] == date(2026, 8, 31)
    assert defaults["granularity"] == "30s"
