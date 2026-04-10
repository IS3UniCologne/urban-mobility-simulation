"""Base class for all ridehailing operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.enums import TaskState
from simulation.operator.operations_management.operations import (
    Operations,
    OperationsDependencies,
)
from simulation.tasks.base.vehicle_session import VehicleSession
from simulation.tasks.operations.autonomous_relocation_task import (
    AutonomousRelocationTask,
)
from simulation.tasks.operations.distributed_charging_task import (
    DistributedChargingTask,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.operator.data_transfer_object import ChargingSession


class RideHailingOperations(Operations):
    """Parent class for all ridehailing operations.

    This class extends the generic Operations class with ridehailing-specific functionality.
    """

    # TODO: Move shared logic here

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)

    def _execute_autonomous_charging_session(
        self, charging_session: ChargingSession
    ) -> Generator[Event, None, None]:
        """Execute autonomous relocation and charging for a vehicle.

        Updates ChargingSession with results from the executed tasks.

        Parameters
        ----------
        charging_session : ChargingSession
            Charging session DTO.
        """
        vehicle = charging_session.vehicle
        geo_env = self._sim.geo_env
        dest_position = GeodesicPosition(
            self._sim,
            *geo_env.get_centroid(charging_session.destination),
            charging_session.destination,
        )
        distance = vehicle.destination << dest_position

        reservation = vehicle.reserve()

        # 1. Create tasks
        relocation_task = AutonomousRelocationTask(
            sim=self._sim, vehicle=vehicle, destination=dest_position, distance=distance
        )

        charging_task = DistributedChargingTask(
            sim=self._sim,
            vehicle=vehicle,
            charging_duration=charging_session.charging_duration,
            charging_station=charging_session.charging_station,
            scheduled_time=charging_session.scheduled_time,
            arrived_at_charging_station=charging_session.arrived_at_charging_station,
            started_charging=charging_session.started_charging,
        )

        # 2. Create Session
        vehicle_session = VehicleSession(
            sim=self._sim,
            vehicle=vehicle,
            reservation=reservation,
            tasks=[relocation_task, charging_task],
            holder=None,
        )

        # 3. Execute Session
        yield from vehicle_session.execute()

        # 4. Update Results
        if charging_task.state is not TaskState.ABORTED:
            charging_session.waiting_time = charging_task.waiting_time
            charging_session.kWh_charged = charging_task.kWh_charged
            charging_session.estimated_completion_time = (
                charging_task.estimated_completion_time
            )

        charging_session.finished.succeed()
