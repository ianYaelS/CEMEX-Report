from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from errors import StorageError


class Storage(Protocol):
    def put(self, Key: str, Body: bytes, **kwargs: Any) -> Any: ...


class LocalStorage:
    backend_name = "local"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, Key: str, Body: bytes, **kwargs: Any) -> dict[str, str]:
        self.objects[Key] = Body
        return {"Key": Key}


class _Wrapper:
    def __init__(self, inner: Any, name: str) -> None:
        self._inner = inner
        self.backend_name = name

    def put(self, Key: str, Body: bytes, **kwargs: Any) -> Any:
        extra = {key: value for key, value in kwargs.items() if value is not None}
        if hasattr(self._inner, "put"):
            try:
                return self._inner.put(Key=Key, Body=Body, **extra)
            except TypeError:
                return self._inner.put(Key=Key, Body=Body)
        if hasattr(self._inner, "save"):
            try:
                return self._inner.save(Key, Body)
            except TypeError:
                return self._inner.save(Key=Key, Body=Body)
        raise StorageError("storage backend has neither put nor save")


class _S3Storage:
    backend_name = "s3"

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, Key: str, Body: bytes, **kwargs: Any) -> Any:
        args: dict[str, Any] = {"Bucket": self._bucket, "Key": Key, "Body": Body}
        if kwargs.get("ContentType"):
            args["ContentType"] = kwargs["ContentType"]
        if kwargs.get("ContentDisposition"):
            args["ContentDisposition"] = kwargs["ContentDisposition"]
        return self._client.put_object(**args)


def in_function_runtime() -> bool:
    return bool(os.environ.get("SamsaraFunctionName") or os.environ.get("SamsaraFunctionStorageName"))


def _from_samsarafnstorage() -> Storage | None:
    try:
        from samsarafnstorage import get_storage as runtime_get_storage

        return _Wrapper(runtime_get_storage(), "samsarafnstorage")
    except Exception:
        return None


def _from_legacy_function() -> Storage | None:
    try:
        import samsara

        return _Wrapper(samsara.Function().storage(), "samsara.Function")
    except Exception:
        return None


def _from_s3() -> Storage | None:
    bucket = os.environ.get("SamsaraFunctionStorageName")
    if not bucket:
        return None
    try:
        import boto3

        kwargs: dict[str, Any] = {}
        role = os.environ.get("SamsaraFunctionExecRoleArn")
        name = os.environ.get("SamsaraFunctionName") or "cemex-telemetry-report"
        if role:
            sts = boto3.client("sts")
            assumed = sts.assume_role(RoleArn=role, RoleSessionName=name[:64])
            creds = assumed["Credentials"]
            kwargs = {
                "aws_access_key_id": creds["AccessKeyId"],
                "aws_secret_access_key": creds["SecretAccessKey"],
                "aws_session_token": creds["SessionToken"],
            }
        return _S3Storage(boto3.client("s3", **kwargs), bucket)
    except Exception:
        return None


def get_storage(*, require_persistent: bool = False) -> Storage:
    for factory in (_from_samsarafnstorage, _from_legacy_function, _from_s3):
        backend = factory()
        if backend is not None:
            return backend
    if require_persistent and in_function_runtime():
        raise StorageError(
            "Function Storage is unavailable (samsarafnstorage/S3). "
            "Open the Function Storage tab after a successful write, or retry the upload."
        )
    return LocalStorage()


def sanitize_segment(value: str, fallback: str = "unidad") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (value or "").strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def sanitize_vehicle_name(name: str) -> str:
    return sanitize_segment(name, "unidad")


def _local_date_stamp(start: datetime, end: datetime, timezone: str) -> str:
    tz = ZoneInfo(timezone)
    start_day = start.astimezone(tz).date()
    last_instant = end - timedelta(microseconds=1)
    end_day = last_instant.astimezone(tz).date()
    if start_day == end_day:
        return start_day.isoformat()
    return f"{start_day.isoformat()}_a_{end_day.isoformat()}"


def storage_object_key(
    prefix: str,
    vehicle_name: str,
    start: datetime,
    end: datetime,
    granularity: str,
    timezone: str,
    *,
    vehicle_id: str = "",
) -> str:
    del granularity
    root = sanitize_segment(prefix, "CEMEX_Reportes")
    unit_id = sanitize_segment(vehicle_id, "sinid")
    unit_name = sanitize_segment(vehicle_name, unit_id)
    folder = unit_name if unit_name != "unidad" else unit_id
    stamp = _local_date_stamp(start, end, timezone)
    filename = f"{stamp}_{unit_id}_{unit_name}.csv"
    return f"{root}/{folder}/{filename}"


def put_bytes(storage: Storage, key: str, body: bytes, *, filename: str | None = None) -> None:
    name = filename or key.rsplit("/", 1)[-1]
    content_type = (
        "text/csv; charset=utf-8" if name.endswith(".csv") else "application/json"
    )
    storage.put(
        Key=key,
        Body=body,
        ContentType=content_type,
        ContentDisposition=f'attachment; filename="{name}"',
    )


def _log(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def persist_report_files(
    storage: Storage,
    *,
    csv_key: str,
    csv_bytes: bytes,
) -> None:
    put_bytes(storage, csv_key, csv_bytes)
    _log(
        {
            "event": "storage",
            "ok": True,
            "backend": getattr(storage, "backend_name", type(storage).__name__),
            "storageKey": csv_key,
            "bytes": len(csv_bytes),
        }
    )
