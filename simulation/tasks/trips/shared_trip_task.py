"""User trip task for shared vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.enums import UserState
from simulation.tasks.base.vehicle_task import VehicleTask

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.data_transfer_object.vehicle_allocation import (
        VehicleAllocation,
    )
    from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedTripTask(VehicleTask["SharedVehicle"]):
    """Shared mobility trip task.

    Lifecycle:
        1. User walks to the parked vehicle
        2. Mount user
        3. Drive to destination
        4. Park and unmount

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : SharedVehicle
        The shared vehicle.
    user : User
        The user taking the trip.
    allocation : VehicleAllocation
        The allocation containing route and pickup info.
    """

    __slots__ = ("_allocation", "_energy_consumed", "_user")

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: SharedVehicle,
        user: User,
        allocation: VehicleAllocation,
    ) -> None:
        super().__init__(sim, vehicle)
        self._user = user
        self._allocation = allocation
        self._energy_consumed: float = 0.0

    @property
    def energy_consumed(self) -> float:
        """Get the energy consumed during the trip."""
        return self._energy_consumed

    def _run(self) -> Generator[Event, None, None]:
        # Walk to vehicle
        # TODO: Let User handle their own state transitions
        self._user.state = UserState.MOVING_TO_VEHICLE
        self._vehicle.wait_for_user()
        yield from self._user.walk_to(self._vehicle.position)

        # Embark
        self._user.state = UserState.IN_TRANSPORT
        self._vehicle.mount_driver(self._user)

        # Transport
        route = self._allocation.transportation_alternative.route
        self._energy_consumed = yield from self._vehicle.traverse_route(route)

        # Disembark
        self._vehicle.park()
        self._vehicle.unmount_driver()

    def get_predicted_energy_delta(self, current_energy: float | None = None) -> float:
        """Calculate predicted energy for driving trip.

        Walking consumes no vehicle energy, so only driving distance counts.

        Parameters
        ----------
        current_energy : float or None
            Unused; trip energy depends on distance only.

        Returns
        -------
        float
            Predicted energy delta in kWh for driving portion.
        """
        drive_distance = self._allocation.transportation_alternative.distance
        energy_required = self._vehicle.energy_system.calculate_energy_required(
            drive_distance
        )
        return -energy_required

    def get_predicted_duration(self, current_energy: float | None = None) -> float:
        """Calculate predicted duration including walk time and driving.

        Parameters
        ----------
        current_energy : float or None
            Unused; trip duration depends on distance only.

        Returns
        -------
        float
            Total predicted duration in minutes (walk + drive).
        """
        alternative = self._allocation.transportation_alternative

        walk_distance = self._user.position << self._vehicle.position
        walk_time = walk_distance / self._user.walking_speed_mm

        # Duration for driving
        drive_duration = alternative.duration

        return walk_time + drive_duration
