from __future__ import annotations

from constants import DEFAULT_GRANULARITY
from params import parse_params


def test_default_granularity_is_30s() -> None:
    params = parse_params(
        {
            "vehicle_id": "1",
            "start_time": "2026-08-31",
            "end_time": "2026-08-31",
        }
    )
    assert DEFAULT_GRANULARITY == "30s"
    assert params.granularity == "30s"
