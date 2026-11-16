"""Unit tests for the ride-hailing search engine."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from simulation.helper.configuration.configuration import RideHailingSearchEngineConfig
from simulation.helper.enums import AutonomyType
from simulation.helper.vehicle_states import VehicleStates
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.operator.search_engine import SearchEngineDependencies

pytestmark = pytest.mark.unit


class PointStub:
    """Position on a straight line."""

    def __init__(self, offset_m: float) -> None:
        self.offset_m = offset_m

    def __lshift__(self, other: PointStub) -> float:
        return abs(self.offset_m - other.offset_m)


class EnergyStub:
    """Energy system that holds enough energy for a fixed range."""

    def __init__(self, range_m: float) -> None:
        self.range_m = range_m

    def has_enough_energy(self, distance: float) -> bool:
        return distance <= self.range_m


class VehicleStub:
    """
    Ride-hailing vehicle that drives 500 meters per minute.

    Parameters
    ----------
    position_m : float
        Offset on the line.
    autonomy_type : AutonomyType
        Human-driven or autonomous.
    range_m : float
        Distance its energy covers.
    is_reserved : bool
        Whether it holds a reservation.
    request : tuple of float or None
        Pickup and dropoff offset of the request in progress.
        None for a vehicle on standby.
    """

    def __init__(
        self,
        position_m: float = 100,
        autonomy_type: AutonomyType = AutonomyType.HUMAN_DRIVEN,
        range_m: float = 100_000,
        is_reserved: bool = False,
        request: tuple[float, float] | None = None,
    ) -> None:
        self.position = PointStub(position_m)
        self.autonomy_type = autonomy_type
        self.energy_system = EnergyStub(range_m)
        self.is_reserved = is_reserved
        self.state = VehicleStates.STANDBY
        self.current_request = None
        self.is_in_use = False
        self.estimated_completion_time = 0.0
        if request is not None:
            self.state = VehicleStates.DRIVING
            self.current_request = SimpleNamespace(
                origin=PointStub(request[0]), destination=PointStub(request[1])
            )
            self.is_in_use = True

    def calculate_travel_time(self, distance: float) -> float:
        return distance / 500


class FleetStub(RideHailingFleet):
    """Ride-hailing fleet over a fixed list of vehicles, without a spatial index."""

    def __init__(self, vehicles: list[VehicleStub]) -> None:
        self._stubs = vehicles

    def parking_vehicles_in_radius(
        self, query_position: PointStub, radius: float
    ) -> list[VehicleStub]:
        return [
            v
            for v in self._stubs
            if v.state is VehicleStates.STANDBY
            and (v.position << query_position) <= radius
        ]

    def expected_arrivals_in_radius(
        self, query_position: PointStub, radius: float, max_eta: float | None = None
    ) -> list[VehicleStub]:
        return [
            v
            for v in self._stubs
            if v.current_request is not None
            and (v.current_request.destination << query_position) <= radius
        ]


def search(
    vehicles: list[VehicleStub], destination_m: float = 6000
) -> dict[VehicleStub, float]:
    """Search a trip from 0 to destination_m and map each offered vehicle to its price."""
    sim = Mock()
    sim.uid_manager.generate_uid.return_value = (1, "uid")
    sim.time = 0.0
    config = RideHailingSearchEngineConfig(
        AV_PRICE_REDUCTION=0.9,
        MAX_PICKUP_DISTANCE=2000,
        PRICE_ENTERING=2.0,
        PRICE_PER_MINUTE=0.35,
        PRICE_PER_KM=1.3,
        MINIMUM_PRICE=5.0,
    )
    operator = SimpleNamespace(fleet=FleetStub(vehicles))
    engine = RideHailingSearchEngine(
        SearchEngineDependencies(sim=sim, config=config, operator=operator)
    )
    request = SimpleNamespace(origin=PointStub(0), destination=PointStub(destination_m))
    browser = engine.search_for_transportation_alternatives(request)
    return {alt.vehicle: alt.price for alt in browser.transportation_alternatives}


class TestRideHailingSearchEngine:
    def test_prices_trip_by_duration_and_distance(self) -> None:
        # 6 km in 12 minutes: 2.0 + 12 * 0.35 + 6 * 1.3
        human_driven = VehicleStub()
        autonomous = VehicleStub(autonomy_type=AutonomyType.AUTONOMOUS)

        prices = search([human_driven, autonomous])

        assert prices == pytest.approx({human_driven: 14.0, autonomous: 12.6})

    def test_charges_minimum_price_for_short_trip(self) -> None:
        # 1 km in 2 minutes: 2.0 + 2 * 0.35 + 1 * 1.3 is below the minimum of 5.0
        human_driven = VehicleStub()
        autonomous = VehicleStub(autonomy_type=AutonomyType.AUTONOMOUS)

        prices = search([human_driven, autonomous], destination_m=1000)

        assert prices == pytest.approx({human_driven: 5.0, autonomous: 4.5})

    def test_offers_only_vehicles_within_pickup_radius(self) -> None:
        at_radius = VehicleStub(position_m=2000)
        beyond_radius = VehicleStub(position_m=2001)
        dropping_off_at_radius = VehicleStub(request=(4000, 2000))
        dropping_off_beyond_radius = VehicleStub(request=(4000, 2001))

        prices = search(
            [
                at_radius,
                beyond_radius,
                dropping_off_at_radius,
                dropping_off_beyond_radius,
            ]
        )

        assert prices.keys() == {at_radius, dropping_off_at_radius}

    def test_offers_only_vehicles_with_energy_for_pickup_and_trip(self) -> None:
        # parking 100 m from the origin: 100 + 6000
        parking = VehicleStub(range_m=6100)
        parking_short = VehicleStub(range_m=6099)
        # dropping off 1000 m from the origin after a 1000 m request: 1000 + 1000 + 6000
        dropping_off = VehicleStub(range_m=8000, request=(2000, 1000))
        dropping_off_short = VehicleStub(range_m=7999, request=(2000, 1000))

        prices = search([parking, parking_short, dropping_off, dropping_off_short])

        assert prices.keys() == {parking, dropping_off}

    def test_skips_reserved_vehicle_only_when_human_driven(self) -> None:
        reserved_human_driven = VehicleStub(is_reserved=True)
        reserved_autonomous = VehicleStub(
            is_reserved=True, autonomy_type=AutonomyType.AUTONOMOUS
        )
        free = VehicleStub()

        prices = search([reserved_human_driven, reserved_autonomous, free])

        assert prices.keys() == {reserved_autonomous, free}

    def test_offers_human_driven_vehicles_first(self) -> None:
        autonomous = VehicleStub(autonomy_type=AutonomyType.AUTONOMOUS)
        human_driven = VehicleStub()

        prices = search([autonomous, human_driven])

        assert list(prices) == [human_driven, autonomous]
