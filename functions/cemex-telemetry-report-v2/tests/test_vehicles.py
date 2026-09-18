from __future__ import annotations

from typing import Any

from vehicles import list_vehicles, vehicle_label


class ScriptedClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_paginated(self, path: str, params: dict[str, str], merge_page) -> list[Any]:
        self.calls.append((path, params))
        collected: list[Any] = []
        merge_page(
            collected,
            {
                "data": [
                    {"id": "2", "name": "FAV76", "licensePlate": "XYZ76"},
                    {"id": "1", "name": "FAV68", "license_plate": "ABC68"},
                    {"id": "3", "name": "SINPLACA"},
                ],
                "pagination": {"hasNextPage": False},
            },
        )
        return collected


def test_list_vehicles_pulls_name_plate_and_id() -> None:
    vehicles = list_vehicles(ScriptedClient())
    assert [item.id for item in vehicles] == ["1", "2", "3"]
    assert vehicles[0].name == "FAV68"
    assert vehicles[0].license_plate == "ABC68"
    assert vehicles[1].license_plate == "XYZ76"
    assert vehicles[2].license_plate == ""
    assert vehicle_label(vehicles[0]) == "FAV68 · ABC68 · 1"
    assert vehicle_label(vehicles[2]) == "SINPLACA · sin placa · 3"
