from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from simulation.helper.vehicle_states import VehicleStates
from simulation.operator.vehicle_allocation_engine import (
    AllocationEngine,
    AllocationEngineDependencies,
)
from simulation.vehicle.mixins.reservable_mixin import ReservableMixin

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
    __slots__ = (
        "_env",
        "_request_arrived",
        "_vehicle_assignment_ids",
        "_vehicle_assignment_requests",
        "_vehicles_assigned_to_users",
    )

    def __init__(self, deps: AllocationEngineDependencies) -> None:
        super().__init__(deps)
        self._env = deps.sim.env
        self._vehicles_assigned_to_users = self._env.event()
        self._request_arrived = self._env.event()
        self._env.process(self.run())
        self._vehicle_assignment_requests: list[
            tuple[User, TransportationAlternative]
        ] = []
        self._vehicle_assignment_ids = set()

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
                if isinstance(requested_alternative.vehicle, ReservableMixin):
                    if (
                        # TODO: Include non-idle vehicles for pre-booking ?
                        requested_alternative.vehicle.state_machine.is_in_state(
                            VehicleStates.IDLE
                        )
                        and not requested_alternative.vehicle.is_reserved
                    ):
                        requested_alternative.vehicle.reserve_for_user(user)
                    else:
                        self.logger.debug(
                            "Vehicle %s not available for assignment (state: %s, reserved: %s)",
                            requested_alternative.vehicle.uid,
                            requested_alternative.vehicle.state,
                            requested_alternative.vehicle.is_reserved,
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
            self._vehicle_assignment_ids.clear()

    def request_vehicle_allocation(
        self, user: User, selected_transportation_alternative: TransportationAlternative
    ) -> Generator[Event, Any, VehicleAllocation | None]:
        """
        Allocate vehicle in transportation alternative to the user.

        If vehicle is still driving (finishing another trip), wait for it to complete before allocation.

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

        # Wait for vehicle to become idle (if not already)
        yield from selected_vehicle.wait_for_idle()

        try:
            self._add_request(user, selected_transportation_alternative)
        except Exception:
            self.logger.debug(
                "Vehicle %s already assigned to another user",
                selected_transportation_alternative.vehicle.uid,
            )
            # Log failed allocation attempt
            # TODO: do we want to filter multiple failed allocation attempts by the same user?
            self._operator.log_failed_allocation_attempt(
                user=user,
                transportation_task=user.transport_task,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

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
                transportation_task=user.transport_task,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

        # TODO: This should not happen but until the state system is fully reliable we keep this check
        if not selected_vehicle.state_machine.is_in_state(VehicleStates.IDLE):
            self.logger.warning(
                "Vehicle %s is no longer IDLE (state: %s), cannot dispatch for user %s",
                selected_vehicle.uid,
                selected_vehicle.state,
                user.uid,
            )
            self._operator.log_failed_allocation_attempt(
                user=user,
                transportation_task=user.transport_task,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

        # TODO: Move this to task
        selected_vehicle.release_reservation()

        # Set vehicle task
        selected_vehicle.set_current_task(user.transport_task)

        # Create allocation object
        vehicle_allocation = VehicleAllocation(
            user,
            selected_transportation_alternative,
            selected_vehicle.position,
            selected_transportation_alternative.est_pickup_time,
        )

        # Dispatch vehicle to pickup location
        self._env.process(selected_vehicle.move_to_pick_up_position(vehicle_allocation))

        # Vehicle was successfully allocated
        return vehicle_allocation

    def _add_request(self, user, vehicle_assignment):  # noqa: ANN001, ANN202
        if vehicle_assignment.vehicle.uid not in self._vehicle_assignment_ids:
            self._vehicle_assignment_requests.append((user, vehicle_assignment))
            self._vehicle_assignment_ids.add(vehicle_assignment.vehicle.uid)
            # Trigger event to wake up allocation engine
            self._request_arrived.succeed()
            self._request_arrived = self._env.event()
        else:
            raise Exception
