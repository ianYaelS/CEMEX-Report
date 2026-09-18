from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from errors import ConfigError
from params import parse_params
from secrets_io import resolve_token
from timeutil import yesterday_in_timezone


def test_missing_vehicle_raises() -> None:
    with pytest.raises(ConfigError, match="vehicle"):
        parse_params({"report_date": "2026-08-31"})


def test_invalid_report_date_raises() -> None:
    with pytest.raises(ConfigError, match="report_date"):
        parse_params({"vehicle_name": "FAV76", "report_date": "31/08/2026"})


def test_unknown_granularity_raises() -> None:
    with pytest.raises(ConfigError, match="granularity"):
        parse_params({"vehicle_name": "FAV76", "granularity": "hourly"})


def test_default_date_is_yesterday_in_timezone() -> None:
    tz_name = "America/Mexico_City"
    now = datetime(2026, 9, 15, 22, 0, tzinfo=ZoneInfo(tz_name))
    params = parse_params({"vehicle_name": "FAV76", "timezone": tz_name}, now=now)
    assert params.report_date == yesterday_in_timezone(tz_name, now=now)
    assert params.report_date.isoformat() == "2026-09-14"


def test_alert_asset_id_is_accepted() -> None:
    params = parse_params(
        {
            "assetId": "281474977075805",
            "reportDate": "2026-08-31",
            "SamsaraFunctionTriggerSource": "alert",
        }
    )
    assert params.vehicle_id == "281474977075805"
    assert params.trigger_source == "alert"


def test_http_api_base_url_rejected() -> None:
    with pytest.raises(ConfigError, match="https"):
        parse_params({"vehicle_name": "FAV76", "api_base_url": "http://api.samsara.com"})


def test_start_and_end_dates_are_local_day_bounds() -> None:
    params = parse_params(
        {
            "vehicle_name": "FAV76",
            "start_time": "2026-08-31",
            "end_time": "2026-08-31",
            "timezone": "America/Mexico_City",
        }
    )
    assert params.report_date.isoformat() == "2026-08-31"
    assert params.start.isoformat() == "2026-08-31T00:00:00-06:00"
    assert params.end.isoformat() == "2026-09-01T00:00:00-06:00"
    assert params.write_storage is True
    assert params.include_csv is False


def test_seven_inclusive_dates_are_seven_local_days() -> None:
    from timeutil import iter_local_day_windows

    params = parse_params(
        {
            "vehicle_id": "1",
            "start_time": "2026-08-31",
            "end_time": "2026-09-06",
            "timezone": "America/Mexico_City",
        }
    )
    windows = iter_local_day_windows(params.start, params.end, params.timezone)
    assert len(windows) == 7
    assert windows[0][0].isoformat() == "2026-08-31T00:00:00-06:00"
    assert windows[-1][1].isoformat() == "2026-09-07T00:00:00-06:00"
    assert (params.end - params.start).days == 7


def test_end_before_start_raises() -> None:
    with pytest.raises(ConfigError, match="end_time"):
        parse_params(
            {
                "vehicle_name": "FAV76",
                "start_time": "2026-09-02",
                "end_time": "2026-08-31",
            }
        )


def test_api_key_event_variable() -> None:
    assert resolve_token({}, environ={}, event={"api_key": "samsara_api_test"}) == "samsara_api_test"
    assert resolve_token({}, environ={}, event={"API_KEY": "samsara_api_test"}) == "samsara_api_test"


def test_secret_wins_over_event_api_key() -> None:
    token = resolve_token(
        {"SAMSARA_API_TOKEN": "from-secret"},
        environ={},
        event={"api_key": "from-event"},
    )
    assert token == "from-secret"


def test_secret_named_api_key_is_accepted() -> None:
    assert resolve_token({"api_key": "samsara_api_secret"}, environ={}, event={}) == (
        "samsara_api_secret"
    )


def test_output_key_prefix_alias() -> None:
    params = parse_params(
        {
            "vehicle_name": "FAV76",
            "report_date": "2026-08-31",
            "output_key_prefix": "reports/daily",
        }
    )
    assert params.storage_prefix == "reports/daily"
