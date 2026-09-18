from __future__ import annotations

from datetime import datetime
from typing import Any

from client import SamsaraClient
from constants import HISTORY_TYPES
from errors import StatsEmptyError
from models import EngineEvent, GpsPoint, OdometerEvent, VehicleHistory, VehicleRef
from timeutil import parse_api_time, to_rfc3339


def _gps_address(point: dict[str, Any]) -> str:
    reverse_geo = point.get("reverseGeo")
    if isinstance(reverse_geo, dict):
        formatted = reverse_geo.get("formattedLocation")
        if formatted:
            return str(formatted)
    address = point.get("address")
    if isinstance(address, dict):
        name = address.get("name")
        if name:
            return str(name)
    return ""


def _parse_gps(items: list[Any]) -> list[GpsPoint]:
    points: list[GpsPoint] = []
    for item in items:
        if not isinstance(item, dict) or "time" not in item:
            continue
        if item.get("latitude") is None or item.get("longitude") is None:
            continue
        speed = item.get("speedMilesPerHour")
        points.append(
            GpsPoint(
                time=parse_api_time(str(item["time"])),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                speed_mph=None if speed is None else float(speed),
                address=_gps_address(item),
                is_ecu_speed=item.get("isEcuSpeed"),
            )
        )
    return points


def _parse_engine(items: list[Any]) -> list[EngineEvent]:
    events: list[EngineEvent] = []
    for item in items:
        if not isinstance(item, dict) or "time" not in item:
            continue
        events.append(
            EngineEvent(
                time=parse_api_time(str(item["time"])),
                value=str(item.get("value") if item.get("value") is not None else ""),
            )
        )
    return events


def _parse_obd(items: list[Any]) -> list[OdometerEvent]:
    # Never read gpsOdometerMeters — OBD only.
    events: list[OdometerEvent] = []
    for item in items:
        if not isinstance(item, dict) or "time" not in item:
            continue
        raw = item.get("value")
        if raw is None:
            continue
        events.append(
            OdometerEvent(
                time=parse_api_time(str(item["time"])),
                meters=float(raw),
            )
        )
    return events


def _find_vehicle_blob(data: list[Any], vehicle_id: str) -> dict[str, Any] | None:
    for item in data:
        if isinstance(item, dict) and str(item.get("id") or "") == vehicle_id:
            return item
    return None


def _merge_history_page(collected: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    data = payload.get("data") or []
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict):
            continue
        vehicle_id = str(item.get("id") or "")
        existing = _find_vehicle_blob(collected, vehicle_id)
        if existing is None:
            collected.append(
                {
                    "id": vehicle_id,
                    "name": item.get("name") or "",
                    "gps": list(item.get("gps") or []),
                    "engineStates": list(item.get("engineStates") or []),
                    "obdOdometerMeters": list(item.get("obdOdometerMeters") or []),
                }
            )
            continue
        existing["gps"].extend(item.get("gps") or [])
        existing["engineStates"].extend(item.get("engineStates") or [])
        existing["obdOdometerMeters"].extend(item.get("obdOdometerMeters") or [])


def parse_history(blob: dict[str, Any], vehicle: VehicleRef) -> VehicleHistory:
    return VehicleHistory(
        vehicle=vehicle,
        gps=_parse_gps(list(blob.get("gps") or [])),
        engine_states=_parse_engine(list(blob.get("engineStates") or [])),
        obd_odometer=_parse_obd(list(blob.get("obdOdometerMeters") or [])),
    )


def fetch_history(
    client: SamsaraClient,
    vehicle: VehicleRef,
    start: datetime,
    end: datetime,
) -> VehicleHistory:
    collected: list[dict[str, Any]] = client.get_paginated(
        "/fleet/vehicles/stats/history",
        {
            "types": HISTORY_TYPES,
            "startTime": to_rfc3339(start),
            "endTime": to_rfc3339(end),
            "vehicleIds": vehicle.id,
        },
        _merge_history_page,
    )
    blob = _find_vehicle_blob(collected, vehicle.id)
    if blob is None and collected:
        blob = collected[0]
    window = f"{to_rfc3339(start)} .. {to_rfc3339(end)}"
    hint = (
        " Confirm api_key is from THIS org, the token can Read Vehicle Statistics, "
        "and the vehicle has GPS in that local day."
    )
    if blob is None:
        raise StatsEmptyError(
            f"no stats for vehicle {vehicle.name} ({vehicle.id}) in {window}.{hint}"
        )
    blob_name = str(blob.get("name") or "").strip()
    if blob_name and blob_name != vehicle.name:
        vehicle = VehicleRef(id=vehicle.id, name=blob_name)
    history = parse_history(blob, vehicle)
    if not history.gps:
        raise StatsEmptyError(
            f"no GPS points for vehicle {vehicle.name} ({vehicle.id}) in {window}.{hint}"
        )
    return history
