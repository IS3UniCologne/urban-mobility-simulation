"""Unit tests for the spatial indexes."""

from __future__ import annotations

import math
import random
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from simulation.environment.geodesic_helper import (
    _NARROW_ABOVE,
    METERS_PER_DEGREE,
    FastSpatialDestinationIndex,
    FastSpatialVehicleIndex,
)
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.enums import VehicleType

pytestmark = pytest.mark.unit


def position(north_m: float, east_m: float = 0.0) -> GeodesicPosition:
    """Build a position a number of meters north and east of a fixed point in Berlin."""
    sim = Mock()
    sim.config.world.SPATIAL_RESOLUTION = 7
    lat = 52.5 + north_m / METERS_PER_DEGREE
    lng = 13.4 + east_m / (METERS_PER_DEGREE * math.cos(math.radians(lat)))
    return GeodesicPosition(sim, lat, lng)


def squared_distance_m2(start: GeodesicPosition, end: GeodesicPosition) -> float:
    """Measure the squared distance the indexes use between two positions."""
    lng, lat = start.getExactLocation(geojson=True)
    end_lng, end_lat = end.getExactLocation(geojson=True)
    dx = (end_lng - lng) * METERS_PER_DEGREE * math.cos(math.radians(lat))
    dy = (end_lat - lat) * METERS_PER_DEGREE
    return dx * dx + dy * dy


def vehicle(
    vehicle_id: int,
    north_m: float,
    vehicle_type: VehicleType = VehicleType.CAR,
    destination_m: float | None = None,
    eta_min: float = 0.0,
    east_m: float = 0.0,
) -> SimpleNamespace:
    """Build a vehicle with the attributes the indexes read."""
    return SimpleNamespace(
        id=vehicle_id,
        vehicle_type=vehicle_type,
        position=position(north_m, east_m),
        destination=None if destination_m is None else position(destination_m),
        estimated_completion_time=eta_min,
    )


def test_radius_search_returns_only_vehicles_within_the_radius() -> None:
    index = FastSpatialVehicleIndex()
    index.insert(vehicle(1, north_m=100))
    index.insert(vehicle(2, north_m=400))

    assert index.radius_search(position(0), 250) == {1}


def test_radius_search_returns_vehicles_east_and_west_within_the_radius() -> None:
    index = FastSpatialVehicleIndex()
    index.insert(vehicle(1, north_m=0, east_m=100))
    index.insert(vehicle(2, north_m=0, east_m=-100))
    index.insert(vehicle(3, north_m=0, east_m=400))
    index.insert(vehicle(4, north_m=0, east_m=-400))

    assert index.radius_search(position(0), 250) == {1, 2}


def test_radius_search_matches_a_scan_of_all_vehicles_in_a_large_index() -> None:
    rng = random.Random(0)
    index = FastSpatialVehicleIndex()
    types = (VehicleType.CAR, VehicleType.SCOOTER, VehicleType.BIKE)
    radius = {VehicleType.CAR: 500, VehicleType.SCOOTER: 300}
    parked = {}
    for vehicle_id in range(_NARROW_ABOVE + 500):
        parked[vehicle_id] = vehicle(
            vehicle_id,
            rng.uniform(-2000, 2000),
            vehicle_type=types[vehicle_id % 3],
            east_m=rng.uniform(-2000, 2000),
        )
        index.insert(parked[vehicle_id])

    for _ in range(50):
        index.delete(parked.pop(rng.choice(list(parked))))
        point = position(rng.uniform(-2000, 2000), rng.uniform(-2000, 2000))

        assert index.radius_search(point, radius) == {
            other.id
            for other in parked.values()
            if other.vehicle_type in radius
            and squared_distance_m2(point, other.position)
            <= radius[other.vehicle_type] ** 2
        }


def test_radius_search_applies_one_radius_per_vehicle_type() -> None:
    index = FastSpatialVehicleIndex()
    index.insert(vehicle(1, north_m=300, vehicle_type=VehicleType.CAR))
    index.insert(vehicle(2, north_m=300, vehicle_type=VehicleType.SCOOTER))
    index.insert(vehicle(3, north_m=100, vehicle_type=VehicleType.BIKE))

    radius = {VehicleType.CAR: 500, VehicleType.SCOOTER: 200}

    assert index.radius_search(position(0), radius) == {1}


def test_delete_keeps_the_other_vehicles_findable() -> None:
    index = FastSpatialVehicleIndex()
    vehicles = [
        vehicle(1, north_m=100, vehicle_type=VehicleType.CAR),
        vehicle(2, north_m=200, vehicle_type=VehicleType.SCOOTER),
        vehicle(3, north_m=300, vehicle_type=VehicleType.BIKE),
    ]
    for inserted in vehicles:
        index.insert(inserted)

    index.delete(vehicles[0])

    assert index.radius_search(position(0), 1000) == {2, 3}
    assert index.radius_search(position(0), {VehicleType.BIKE: 1000}) == {3}
    index.insert(vehicles[0])
    assert index.radius_search(position(0), 1000) == {1, 2, 3}


def test_index_holds_more_vehicles_than_its_first_capacity() -> None:
    index = FastSpatialVehicleIndex()
    for vehicle_id in range(200):
        index.insert(vehicle(vehicle_id, north_m=vehicle_id))

    assert index.radius_search(position(0), 1000) == set(range(200))


def test_delete_refuses_a_vehicle_that_moved() -> None:
    index = FastSpatialVehicleIndex()
    moved = vehicle(1, north_m=100)
    index.insert(moved)
    moved.position = position(500)

    with pytest.raises(RuntimeError, match="position changed"):
        index.delete(moved)


def test_destination_search_leaves_out_late_and_distant_arrivals() -> None:
    index = FastSpatialDestinationIndex()
    index.insert(vehicle(1, north_m=5000, destination_m=100, eta_min=10))
    index.insert(vehicle(2, north_m=5000, destination_m=100, eta_min=30))
    index.insert(vehicle(3, north_m=5000, destination_m=3000, eta_min=10))

    assert index.radius_search(position(0), 500, max_eta=20) == {1}
    assert index.radius_search(position(0), 500) == {1, 2}


def test_destination_insert_moves_a_vehicle_already_held() -> None:
    index = FastSpatialDestinationIndex()
    rerouted = vehicle(1, north_m=5000, destination_m=100)
    index.insert(rerouted)
    rerouted.destination = position(3000)

    index.insert(rerouted)

    assert index.radius_search(position(0), 500) == set()
    assert index.radius_search(position(3000), 500) == {1}
