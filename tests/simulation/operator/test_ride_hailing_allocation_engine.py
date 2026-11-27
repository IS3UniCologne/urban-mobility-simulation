"""Unit tests for the ride-hailing allocation engine."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import simpy

from simulation.helper.vehicle_states import VehicleStates
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.vehicle_allocation_engine import AllocationEngineDependencies
from simulation.tasks.trips.ride_hailing_trip_task import RideHailingTripTask
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

pytestmark = pytest.mark.unit


class PointStub:
    """Position on a straight line."""

    def __init__(self, offset_m: float) -> None:
        self.offset_m = offset_m

    def __lshift__(self, other: PointStub) -> float:
        return abs(self.offset_m - other.offset_m)


def vehicle_stub(position_m: float, *, is_driving: bool) -> Mock:
    """Ride-hailing vehicle at position_m that drives 500 meters per minute."""
    vehicle = Mock(spec=RideHailingVehicle)
    vehicle.position = PointStub(position_m)
    vehicle.is_reserved = False
    vehicle.is_in_use = is_driving
    vehicle.state = VehicleStates.DRIVING if is_driving else VehicleStates.STANDBY
    vehicle.energy_system.has_enough_energy.return_value = True
    vehicle.reserve.side_effect = lambda requester: setattr(
        vehicle, "reserved_for_user", requester
    )
    vehicle.calculate_travel_time.side_effect = lambda distance: distance / 500
    return vehicle


class TestRideHailingAllocationEngine:
    @pytest.mark.parametrize(
        ("position_at_booking_m", "is_driving"),
        [
            pytest.param(5000, False, id="parked"),
            # its trip started at 0 and drops off at 5000
            pytest.param(0, True, id="booked-mid-trip"),
        ],
    )
    def test_predicted_trip_includes_pickup_leg_from_session_start(
        self, position_at_booking_m: float, is_driving: bool
    ) -> None:
        env = simpy.Environment()
        sim = Mock(env=env)
        sim.uid_manager.generate_uid.return_value = (1, "uid")
        engine = RideHailingAllocationEngine(
            AllocationEngineDependencies(sim=sim, config=Mock(), operator=Mock())
        )
        vehicle = vehicle_stub(position_at_booking_m, is_driving=is_driving)
        user = Mock()
        user.transport_request.origin = PointStub(6000)
        alternative = SimpleNamespace(
            vehicle=vehicle,
            distance=3000,
            duration=6.0,
            route=SimpleNamespace(destination=PointStub(9000)),
            route_to_pickup=SimpleNamespace(distance=1000),
            est_pickup_time=None,
        )

        allocation = env.process(engine.request_vehicle_allocation(user, alternative))
        env.run(until=2)
        # the session starts once the vehicle stands at 5000
        vehicle.position = PointStub(5000)
        task = RideHailingTripTask(sim, vehicle, user, allocation.value)

        # 1000 m pickup leg in 2 minutes, then the 6 minute trip
        assert task.get_predicted_duration() == pytest.approx(8.0)
