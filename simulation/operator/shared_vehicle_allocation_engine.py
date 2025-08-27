from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )

from simulation.helper.configuration.enums import VehicleState
from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    AllocationEngineInterface,
)


class SharedVehicleAllocationEngine(AllocationEngineInterface):  # noqa: D101
    __slots__ = (
        "_env",
        "_sim",
        "_vehicle_assignment_requests",
        "_vehicles_assigned_to_users",
    )

    def __init__(self, sim: SimulationContext) -> None:
        self._sim = sim
        self._env = sim.env
        self._vehicles_assigned_to_users = self._env.event()
        self._env.process(self.run())
        self._vehicle_assignment_requests = []

    def run(self):  # noqa: ANN201, D102
        while True:
            yield self._env.timeout(2)

            # ################## # ###################### #
            # Matching Algorithm : First Come First Serve #
            # ################## # ###################### #

            # First Come First Serve - Assign vehicles to first request
            for user, requests in self._vehicle_assignment_requests:
                if requests.vehicle.state == VehicleState.PARKING:
                    requests.vehicle.reserve(user)

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
            return None

        # Vehicle was succesfully allocated
        return VehicleAllocation(
            user,
            selected_vehicle,
            selected_transportation_alternative,
            selected_vehicle.position,
            None,
        )

    def notify_user_arrival_at_pick_up_position(  # noqa: ANN201, D102
        self, vehicle_assignment: VehicleAllocation
    ):
        pass
        # TODO: What is this ?
        # For Autonomous Vehicles or Mass Transit (i.e., listen to position of vehicle)
        # old_position = vehicle_assignment.vehicle.position
        # from simulation.environment.geodesic_position import GeodesicPosition
        # vehicle_assignment.vehicle.position = GeodesicPosition(65.3, 13.3)
        # self._env.process(self.test(vehicle_assignment, old_position))
