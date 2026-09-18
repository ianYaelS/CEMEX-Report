from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from storage_io import LocalStorage, persist_report_files, storage_object_key


def test_storage_key_uses_cemex_folder_per_unit() -> None:
    tz = "America/Mexico_City"
    start = datetime(2026, 8, 31, tzinfo=ZoneInfo(tz))
    end = datetime(2026, 9, 1, tzinfo=ZoneInfo(tz))
    key = storage_object_key(
        "CEMEX_Reportes",
        "FAV68",
        start,
        end,
        "minute",
        tz,
        vehicle_id="281475002878096",
    )
    assert key == "CEMEX_Reportes/FAV68/2026-08-31_281475002878096_FAV68.csv"


def test_storage_key_range_uses_spanish_a() -> None:
    tz = "America/Mexico_City"
    start = datetime(2026, 8, 31, tzinfo=ZoneInfo(tz))
    end = datetime(2026, 9, 3, tzinfo=ZoneInfo(tz))
    key = storage_object_key(
        "CEMEX_Reportes",
        "Unidad -> #001",
        start,
        end,
        "minute",
        tz,
        vehicle_id="281474999306395",
    )
    assert key == "CEMEX_Reportes/Unidad_-_001/2026-08-31_a_2026-09-02_281474999306395_Unidad_-_001.csv"


def test_persist_writes_csv_and_json() -> None:
    storage = LocalStorage()
    persist_report_files(
        storage,
        csv_key="CEMEX_Reportes/FAV68/2026-08-31_281475002878096_FAV68.csv",
        csv_bytes=b"\xef\xbb\xbfFecha y hora;x\n",
    )
    assert list(storage.objects) == [
        "CEMEX_Reportes/FAV68/2026-08-31_281475002878096_FAV68.csv"
    ]
    assert storage.objects[
        "CEMEX_Reportes/FAV68/2026-08-31_281475002878096_FAV68.csv"
    ].startswith(b"\xef\xbb\xbf")
