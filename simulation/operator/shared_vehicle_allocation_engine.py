from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from simulation.operator.vehicle_allocation_engine import (
    AllocationEngine,
    AllocationEngineDependencies,
)
from simulation.vehicle.mixins.reservable_mixin import ReservableMixin

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )

from simulation.helper.configuration.enums import VehicleState
from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)


class SharedVehicleAllocationEngine(AllocationEngine):  # noqa: D101
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

    def run(self):  # noqa: ANN201, D102
        while True:
            yield self._env.timeout(2)

            # ################## # ###################### #
            # Matching Algorithm : First Come First Serve #
            # ################## # ###################### #

            # First Come First Serve - Assign vehicles to first request
            for user, requested_alternative in self._vehicle_assignment_requests:
                if isinstance(requested_alternative.vehicle, ReservableMixin):
                    # TODO: vehicle state check should be handled in reserve method
                    if requested_alternative.vehicle.state == VehicleState.PARKING:
                        requested_alternative.vehicle.reserve(user)
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
    ) -> VehicleAllocation:
        """
            Assign vehicle in transportation alternative to user
        :param user:
        :param selected_transportation_alternative:
        :return:
        """  # noqa: D205, D400
        self._vehicle_assignment_requests.append(
            (user, selected_transportation_alternative)
        )

        yield self._vehicles_assigned_to_users

        selected_vehicle = selected_transportation_alternative.vehicle

        # No Vehicle Allocation
        if selected_vehicle.reserved_for_user != user:
            # Log failed allocation attempt
            self._operator.log_failed_allocation_attempt(
                user=user,
                transportation_task=user.transport_task,
                transportation_alternative=selected_transportation_alternative,
            )
            return None

        # Vehicle was succesfully allocated
        return VehicleAllocation(
            user=user,
            transportation_alternative=selected_transportation_alternative,
            pick_up_position=selected_vehicle.position,
            pick_up_time=None,
        )
