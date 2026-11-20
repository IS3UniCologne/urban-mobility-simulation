"""Unit tests for the vehicle fleet."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import simpy

from simulation.helper.enums import AutonomyType, VehicleType
from simulation.helper.exceptions import VehicleFleetError
from simulation.helper.vehicle_states import VehicleStates
from simulation.operator.vehicle_fleet import VehicleFleet, VehicleFleetDependencies

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import VehicleConfig

pytestmark = pytest.mark.unit


class PositionStub:
    """Position at fixed coordinates."""

    def getExactLocation(self, geojson: bool = False) -> tuple[float, float]:
        return (13.4, 52.5)


class VehicleStub:
    """Parked car with the attributes a fleet reads at registration."""

    def __init__(self, vehicle_id: int) -> None:
        self.id = vehicle_id
        self.vehicle_type = VehicleType.CAR
        self.autonomy_type = AutonomyType.HUMAN_DRIVEN
        self.state = VehicleStates.STANDBY
        self.current_region = "region"
        self.position = PositionStub()


class FleetStub(VehicleFleet):
    """Fleet that creates no vehicles of its own."""

    def _create_vehicle(
        self,
        deps: VehicleFleetDependencies,
        position: GeodesicPosition,
        vehicle_config: VehicleConfig,
    ) -> None:
        raise NotImplementedError


def fleet() -> FleetStub:
    """Build an empty fleet in a mocked simulation."""
    sim = Mock()
    sim.uid_manager.generate_uid.return_value = (0, "FleetStub_0")
    sim.env = simpy.Environment()
    return FleetStub(
        VehicleFleetDependencies(operator=Mock(), sim=sim, world=Mock(), config=Mock())
    )


def test_register_vehicle_refuses_a_vehicle_already_in_the_fleet() -> None:
    vehicles = fleet()
    first, second = VehicleStub(1), VehicleStub(2)
    vehicles.register_vehicle(first)
    vehicles.register_vehicle(second)

    with pytest.raises(VehicleFleetError, match="already registered"):
        vehicles.register_vehicle(first)

    assert vehicles.vehicles == [first, second]
