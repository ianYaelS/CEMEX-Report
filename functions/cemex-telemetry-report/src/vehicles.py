from __future__ import annotations

import json
from typing import Any

from client import SamsaraClient
from errors import ApiError, VehicleNotFoundError
from models import VehicleRef


def _log(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def _entity_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                return item
        return None
    if any(key in payload for key in ("id", "name")):
        return payload
    return None


def _vehicle_from_payload(payload: dict[str, Any], fallback_id: str) -> VehicleRef:
    data = _entity_from_payload(payload)
    if data is None:
        raise ApiError("vehicle payload missing data")
    vehicle_id = str(data.get("id") or fallback_id).strip()
    name = str(data.get("name") or "").strip()
    if not vehicle_id:
        raise ApiError("vehicle payload missing id")
    return VehicleRef(id=vehicle_id, name=name or vehicle_id)


def _lookup(
    client: SamsaraClient,
    *,
    path: str,
    params: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    try:
        payload = client.request_json("GET", path, params)
    except ApiError as exc:
        if exc.status_code == 401:
            raise ApiError(
                f"API token rejected on {path}. Use an api_key from THIS organization "
                "with Read Vehicles and Read Vehicle Statistics.",
                401,
            ) from exc
        if exc.status_code in {403, 404}:
            return None, exc.status_code, str(exc)
        raise
    return payload, 200, None


def get_vehicle_by_id(client: SamsaraClient, vehicle_id: str) -> VehicleRef:
    attempts = (
        ("vehicle_path", f"/fleet/vehicles/{vehicle_id}", None),
        ("vehicle_list_ids", "/fleet/vehicles", {"ids": vehicle_id}),
        ("assets", "/assets", {"ids": vehicle_id}),
        ("assets_vehicle", "/assets", {"type": "vehicle", "ids": vehicle_id}),
    )
    last_status: int | None = None
    last_error: str | None = None
    for source, path, params in attempts:
        payload, status, error = _lookup(client, path=path, params=params)
        last_status = status
        last_error = error
        if payload is None:
            _log(
                {
                    "event": "vehicle_lookup",
                    "ok": False,
                    "source": source,
                    "path": path,
                    "status": status,
                }
            )
            continue
        try:
            vehicle = _vehicle_from_payload(payload, vehicle_id)
        except ApiError:
            continue
        if vehicle.id != vehicle_id and str(vehicle.id) != str(vehicle_id):
            continue
        _log(
            {
                "event": "vehicle_lookup",
                "ok": True,
                "source": source,
                "path": path,
                "vehicleId": vehicle.id,
                "vehicleName": vehicle.name,
            }
        )
        return vehicle
    raise VehicleNotFoundError(
        f"vehicle not found: {vehicle_id} "
        f"(lastStatus={last_status}, lastError={last_error})"
    )


def _merge_vehicle_page(collected: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    data = payload.get("data") or []
    if isinstance(data, list):
        collected.extend(item for item in data if isinstance(item, dict))


def find_vehicle_by_name(client: SamsaraClient, vehicle_name: str) -> VehicleRef:
    wanted = vehicle_name.strip()
    wanted_lower = wanted.lower()
    vehicles: list[dict[str, Any]] = client.get_paginated(
        "/fleet/vehicles",
        {},
        _merge_vehicle_page,
    )
    exact: VehicleRef | None = None
    ci_match: VehicleRef | None = None
    for item in vehicles:
        name = str(item.get("name") or "").strip()
        vehicle_id = str(item.get("id") or "").strip()
        if not vehicle_id or not name:
            continue
        if name == wanted:
            exact = VehicleRef(id=vehicle_id, name=name)
            break
        if ci_match is None and name.lower() == wanted_lower:
            ci_match = VehicleRef(id=vehicle_id, name=name)
    found = exact or ci_match
    if found is None:
        raise VehicleNotFoundError(f"vehicle not found: {vehicle_name}")
    return found


def resolve_vehicle(
    client: SamsaraClient,
    *,
    vehicle_id: str | None,
    vehicle_name: str | None,
    trigger_source: str | None = None,
) -> VehicleRef:
    del trigger_source
    if vehicle_id:
        try:
            vehicle = get_vehicle_by_id(client, vehicle_id)
        except VehicleNotFoundError as exc:
            _log(
                {
                    "event": "vehicle_lookup",
                    "ok": False,
                    "source": "id_fallback",
                    "vehicleId": vehicle_id,
                    "error": str(exc),
                }
            )
            return VehicleRef(id=vehicle_id, name=(vehicle_name or vehicle_id))
        if vehicle_name and (not vehicle.name or vehicle.name == vehicle.id):
            return VehicleRef(id=vehicle.id, name=vehicle_name)
        return vehicle
    if vehicle_name:
        return find_vehicle_by_name(client, vehicle_name)
    raise VehicleNotFoundError("vehicle_id is required")
