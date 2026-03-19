"""VehicleTask for ride-hailing vehicle trips."""

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
    from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class RideHailingTripTask(VehicleTask["RideHailingVehicle"]):
    """User trip on a ride-hailing vehicle.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : RideHailingVehicle
        The ride-hailing vehicle.
    user : User
        The user taking the trip.
    allocation : VehicleAllocation
        The allocation containing route and pickup info.
    """

    __slots__ = ("_allocation", "_energy_consumed", "_user", "_vehicle_arrival_time")

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: RideHailingVehicle,
        user: User,
        allocation: VehicleAllocation,
    ) -> None:
        super().__init__(sim, vehicle)
        self._user = user
        self._allocation = allocation
        self._energy_consumed: float = 0.0
        self._vehicle_arrival_time: float | None = None

    @property
    def energy_consumed(self) -> float:
        """Get the energy consumed during the trip."""
        return self._energy_consumed

    @property
    def vehicle_arrival_time(self) -> float | None:
        """Get the time the vehicle arrived at the pickup location."""
        return self._vehicle_arrival_time

    def _run(self) -> Generator[Event, None, None]:
        """Execute the ride-hailing trip lifecycle.

        1. Dispatch vehicle to user's pickup location and wait
        2. Mount user as passenger
        3. Drive user to destination
        4. Park vehicle and unmount passenger

        Yields
        ------
        Event
            SimPy events during the trip.
        """
        # Rendezvous
        self._user.state = UserState.WAITING_FOR_VEHICLE
        self._vehicle.set_current_request(self._user.transport_request)
        self._env.process(self._vehicle.move_to_pick_up_position(self._allocation))
        yield self._vehicle._arrived_at_pick_up_position  # noqa: SLF001
        self._vehicle_arrival_time = self._env.now

        # Embrak
        self._user.state = UserState.IN_TRANSPORT
        self._vehicle.mount_passenger(self._user)

        # Transport
        route = self._allocation.transportation_alternative.route
        self._vehicle.start_driving()
        self._energy_consumed = yield from self._vehicle.traverse_route(route)

        # Disembark
        self._vehicle.park()
        self._vehicle.unmount_passenger(self._user)

    def get_predicted_energy_delta(self, current_energy: float | None = None) -> float:
        """Calculate predicted energy for pickup and transport.

        Parameters
        ----------
        current_energy : float or None
            Unused; trip energy depends on distance only.

        Returns
        -------
        float
            Total predicted energy delta in kWh (pickup + transport).
        """
        alternative = self._allocation.transportation_alternative

        pickup_energy = self._vehicle.energy_system.calculate_energy_required(
            self._vehicle.position << self._allocation.pick_up_position
        )

        transport_energy = self._vehicle.energy_system.calculate_energy_required(
            alternative.distance
        )

        return -(pickup_energy + transport_energy)

    def get_predicted_duration(self, current_energy: float | None = None) -> float:
        """Calculate predicted duration for pickup and transport.

        Parameters
        ----------
        current_energy : float or None
            Unused; trip duration depends on distance only.

        Returns
        -------
        float
            Total predicted duration in minutes (pickup + transport).
        """
        alternative = self._allocation.transportation_alternative

        pickup_distance = self._vehicle.position << self._allocation.pick_up_position
        pickup_duration = self._vehicle.calculate_travel_time(pickup_distance)

        transport_duration = alternative.duration

        return pickup_duration + transport_duration
