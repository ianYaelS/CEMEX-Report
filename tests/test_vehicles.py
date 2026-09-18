from __future__ import annotations

from typing import Any

import pytest

from errors import ApiError
from vehicles import get_vehicle_by_id, resolve_vehicle


class ScriptedClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def request_json(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        del method
        self.calls.append((path, params))
        key = path if params is None else f"{path}?{params}"
        if key not in self.responses:
            key = path
        result = self.responses[key]
        if isinstance(result, Exception):
            raise result
        return result


def test_get_vehicle_by_id_uses_path() -> None:
    client = ScriptedClient(
        {"/fleet/vehicles/281475002878096": {"data": {"id": "281475002878096", "name": "T1"}}}
    )
    vehicle = get_vehicle_by_id(client, "281475002878096")
    assert vehicle.name == "T1"
    assert client.calls[0][0] == "/fleet/vehicles/281475002878096"


def test_get_vehicle_by_id_falls_back_to_assets() -> None:
    client = ScriptedClient(
        {
            "/fleet/vehicles/9": ApiError("HTTP 404", 404),
            "/fleet/vehicles": ApiError("HTTP 404", 404),
            "/assets": {"data": [{"id": "9", "name": "Mixer"}]},
        }
    )
    vehicle = get_vehicle_by_id(client, "9")
    assert vehicle.name == "Mixer"


def test_resolve_vehicle_uses_id_when_catalog_404s() -> None:
    client = ScriptedClient(
        {
            "/fleet/vehicles/9": ApiError("HTTP 404", 404),
            "/fleet/vehicles": ApiError("HTTP 404", 404),
            "/assets": ApiError("HTTP 404", 404),
        }
    )
    vehicle = resolve_vehicle(client, vehicle_id="9", vehicle_name=None)
    assert vehicle.id == "9"
    assert vehicle.name == "9"


def test_get_vehicle_by_id_401_explains_token() -> None:
    client = ScriptedClient({"/fleet/vehicles/9": ApiError("HTTP 401", 401)})
    with pytest.raises(ApiError, match="THIS organization"):
        get_vehicle_by_id(client, "9")
