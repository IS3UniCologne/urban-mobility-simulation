"""Vehicle allocation engine for shared mobility operators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from simulation.operator.vehicle_allocation_engine import (
    AllocationEngine,
    AllocationEngineDependencies,
)
from simulation.vehicle.interfaces.reservable_interface import ReservableInterface

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user import User
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )

from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)


class SharedVehicleAllocationEngine(AllocationEngine):
    """
    Batched first-come-first-serve allocation of shared vehicles.

    Collects allocation requests and resolves them every two simulation
    minutes by reserving each requested vehicle for the first requester.

    Parameters
    ----------
    deps : AllocationEngineDependencies
        Shared allocation engine dependencies.
    """

    __slots__ = (
        "_env",
        "_sim",
        "_vehicle_assignment_requests",
        "_vehicles_assigned_to_users",
    )

    def __init__(self, deps: AllocationEngineDependencies) -> None:
        super().__init__(deps)
        self._sim = deps.sim
        self._env = self._sim.env
        self._vehicles_assigned_to_users = self._env.event()
        self._env.process(self.run())
        self._vehicle_assignment_requests: list[
            tuple[User, TransportationAlternative]
        ] = []

    def run(self) -> Generator[Event, None, None]:
        """
        Process queued allocation requests in batches.

        Yields
        ------
        Event
            Timeout between allocation batches.
        """
        while True:
            yield self._env.timeout(
                2
            )  # TODO: Make configurable ? Why is this 2, while ridehailing has 1?

            if not self._vehicle_assignment_requests:
                # no requests to process
                continue

            # ################## # ###################### #
            # Matching Algorithm : First Come First Serve #
            # ################## # ###################### #

            # First Come First Serve - Assign vehicles to first request
            for user, requested_alternative in self._vehicle_assignment_requests:
                if isinstance(requested_alternative.vehicle, ReservableInterface):
                    if (
                        not requested_alternative.vehicle.is_reserved
                        and requested_alternative.vehicle.energy_system.has_enough_energy(
                            requested_alternative.distance
                        )
                    ):
                        requested_alternative.vehicle.reserve(user)
                    else:
                        self.logger.debug(
                            "Vehicle %s not available for assignment (reserved: %s, in_use: %s)",
                            requested_alternative.vehicle.uid,
                            requested_alternative.vehicle.is_reserved,
                            requested_alternative.vehicle.is_in_use,
                        )
                else:
                    self.logger.warning(
                        "Vehicle %s does not support reservation",
                        requested_alternative.vehicle.uid,
                    )

            # Implement: First come First Serve
            self._vehicles_assigned_to_users.succeed()
            self._vehicles_assigned_to_users = self._env.event()
            self._vehicle_assignment_requests.clear()

    def request_vehicle_allocation(
        self, user: User, selected_transportation_alternative: TransportationAlternative
    ) -> Generator[Event, Any, VehicleAllocation | None]:
        """
        Allocate vehicle in transportation alternative to the user.

        Parameters
        ----------
        user : User
            User requesting vehicle allocation.
        selected_transportation_alternative : TransportationAlternative
            Alternative containing the vehicle to allocate.

        Yields
        ------
        Event
            Batch completion event.

        Returns
        -------
        VehicleAllocation or None
            Vehicle allocation if successful, None otherwise.
        """
        selected_vehicle = selected_transportation_alternative.vehicle
        if not isinstance(selected_vehicle, ReservableInterface):
            self.logger.warning(
                "Vehicle %s does not support reservation", selected_vehicle.uid
            )
            self._operator.log_failed_allocation_attempt(
                user=user,
                transportation_task=user.transport_request,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

        self._vehicle_assignment_requests.append(
            (user, selected_transportation_alternative)
        )

        required_distance = selected_transportation_alternative.distance

        yield self._vehicles_assigned_to_users

        # No Vehicle Allocation
        if selected_vehicle.reserved_for_user != user:
            # Log failed allocation attempt
            self._operator.log_failed_allocation_attempt(
                user=user,
                transportation_task=user.transport_request,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

        if (
            selected_vehicle.is_in_use
            and not selected_vehicle.energy_system.has_enough_energy(required_distance)
        ):
            canceled = selected_vehicle.cancel_queued_user_reservation(
                reason="allocation-revalidation:insufficient-energy"
            )
            self.logger.debug(
                "Allocation revalidation failed for vehicle %s and user %s (required_distance=%.2f, current=%.2f, predicted=%.2f, canceled=%s).",
                selected_vehicle.uid,
                user.uid,
                required_distance,
                selected_vehicle.energy_system.current_energy_absolute,
                selected_vehicle.energy_system.predicted_energy,
                canceled,
            )
            self._operator.log_failed_allocation_attempt(
                user=user,
                transportation_task=user.transport_request,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

        return VehicleAllocation(
            user=user,
            transportation_alternative=selected_transportation_alternative,
            pick_up_position=selected_vehicle.position,
            pick_up_time=None,
        )
