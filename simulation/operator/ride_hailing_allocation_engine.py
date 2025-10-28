from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from simulation.operator.vehicle_allocation_engine import (
    AllocationEngine,
    AllocationEngineDependencies,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user import User
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )

from simulation.helper.configuration.enums import VehicleState
from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)


class RideHailingAllocationEngine(AllocationEngine):  # noqa: D101
    __slots__ = (
        "_env",
        "_vehicle_assignment_ids",
        "_vehicle_assignment_requests",
        "_vehicles_assigned_to_users",
    )

    def __init__(self, deps: AllocationEngineDependencies) -> None:
        super().__init__(deps)
        self._env = deps.sim.env
        self._vehicles_assigned_to_users = self._env.event()
        self._env.process(self.run())
        self._vehicle_assignment_requests = []
        self._vehicle_assignment_ids = set()

    def run(self):  # noqa: ANN201, D102
        while True:
            yield self._env.timeout(1)

            # ################## # ###################### #
            # Matching Algorithm : First Come First Serve #
            # ################## # ###################### #

            # First Come First Serve - Assign vehicles to first request
            for user, requests in self._vehicle_assignment_requests:
                if requests.vehicle.state == VehicleState.PARKING:
                    requests.vehicle.reserve(user)
                else:
                    self.logger.debug(
                        "Vehicle %s is not available for assignment",
                        requests.vehicle.uid,
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

        # If vehicle is finishing another trip, wait for it to complete
        if selected_vehicle.state == VehicleState.DRIVING:
            self.logger.debug(
                "Vehicle %s is currently driving. Waiting for trip completion before allocation.",
                selected_vehicle.uid,
            )
            yield selected_vehicle._driving_finished  # noqa: SLF001
            self.logger.debug(
                "Vehicle %s finished driving. Proceeding with allocation.",
                selected_vehicle.uid,
            )

        try:
            self._add_request(user, selected_transportation_alternative)
        except Exception:
            self.logger.debug(
                "Vehicle %s already assigned to another user",
                selected_transportation_alternative.vehicle.uid,
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
            return None

        # Set vehicle task
        selected_vehicle.set_current_task(user.transport_task)

        # Create allocation object
        vehicle_allocation = VehicleAllocation(
            user,
            selected_vehicle,
            selected_transportation_alternative,
            selected_vehicle.position,
            selected_transportation_alternative.pick_up_time,
        )

        # Dispatch vehicle to pickup location
        self._env.process(selected_vehicle.move_to_pick_up_position(vehicle_allocation))

        # Vehicle was successfully allocated
        return vehicle_allocation

    def _add_request(self, user, vehicle_assignment):  # noqa: ANN001, ANN202
        if vehicle_assignment.vehicle.uid not in self._vehicle_assignment_ids:
            self._vehicle_assignment_requests.append((user, vehicle_assignment))
            self._vehicle_assignment_ids.add(vehicle_assignment.vehicle.uid)
        else:
            raise Exception
