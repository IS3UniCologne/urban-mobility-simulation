from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from simulation.helper.vehicle_states import VehicleStates
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


class RideHailingAllocationEngine(AllocationEngine):  # noqa: D101
    __slots__ = ("_env", "_vehicle_assignment_requests", "_vehicles_assigned_to_users")

    def __init__(self, deps: AllocationEngineDependencies) -> None:
        super().__init__(deps)
        self._env = deps.sim.env
        self._vehicles_assigned_to_users = self._env.event()
        self._env.process(self.run())
        self._vehicle_assignment_requests: list[
            tuple[User, TransportationAlternative]
        ] = []

    def run(self):  # noqa: ANN201, D102
        while True:
            yield self._env.timeout(1)

            if not self._vehicle_assignment_requests:
                # no requests to process
                continue

            # ################## # ###################### #
            # Matching Algorithm : First Come First Serve #
            # ################## # ###################### #

            # First Come First Serve - Assign vehicles to first request
            for user, requested_alternative in self._vehicle_assignment_requests:
                vehicle = requested_alternative.vehicle
                if isinstance(vehicle, ReservableInterface):
                    reservable = (
                        vehicle.is_in_use or vehicle.state is VehicleStates.STANDBY
                    )
                    pickup_distance = (
                        requested_alternative.route_to_pickup.distance
                        if requested_alternative.route_to_pickup
                        else 0.0
                    )
                    total_distance = requested_alternative.distance + pickup_distance
                    if (
                        not vehicle.is_reserved
                        and reservable
                        and vehicle.energy_system.has_enough_energy(total_distance)
                    ):
                        vehicle.reserve(user)
                    else:
                        self.logger.debug(
                            "Vehicle %s not available for assignment.", vehicle.uid
                        )
                else:
                    self.logger.warning(
                        "Vehicle %s does not support reservation.",
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
            The user requesting vehicle allocation.
        selected_transportation_alternative : TransportationAlternative
            The selected transportation alternative containing the vehicle.

        Returns
        -------
        VehicleAllocation or None
            Vehicle allocation if successful, None otherwise.
        """
        selected_vehicle = selected_transportation_alternative.vehicle
        pickup_distance = (
            selected_transportation_alternative.route_to_pickup.distance
            if selected_transportation_alternative.route_to_pickup
            else 0.0
        )
        total_distance = selected_transportation_alternative.distance + pickup_distance

        self._add_request(user, selected_transportation_alternative)
        yield self._vehicles_assigned_to_users

        # No Vehicle Allocation - vehicle was allocated to a different user in the batch
        if selected_vehicle.reserved_for_user != user:
            self.logger.debug(
                "Vehicle %s was allocated to user %s instead of %s",
                selected_vehicle.uid,
                selected_vehicle.reserved_for_user.uid
                if selected_vehicle.reserved_for_user
                else "None",
                user.uid,
            )
            # Log failed allocation attempt
            self._operator.log_failed_allocation_attempt(
                user=user,
                transportation_task=user.transport_request,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

        # Revalidate feasibility at grant time for queued reservations on in-use vehicles.
        if (
            selected_vehicle.is_in_use
            and not selected_vehicle.energy_system.has_enough_energy(total_distance)
        ):
            canceled = selected_vehicle.cancel_queued_user_reservation(
                reason="allocation-revalidation:insufficient-energy"
            )
            self.logger.debug(
                "Allocation revalidation failed for vehicle %s and user %s (required_distance=%.2f, current=%.2f, predicted=%.2f, canceled=%s).",
                selected_vehicle.uid,
                user.uid,
                total_distance,
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

        vehicle_allocation = VehicleAllocation(
            user,
            selected_transportation_alternative,
            selected_vehicle.position,
            selected_transportation_alternative.est_pickup_time,
        )

        # Vehicle was successfully allocated
        return vehicle_allocation

    def _add_request(self, user, vehicle_assignment):  # noqa: ANN001, ANN202
        self._vehicle_assignment_requests.append((user, vehicle_assignment))
