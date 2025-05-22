import logging

from simulation.agent.user import RideHailingUser
from simulation.helper.configuration.enums import VehicleState
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)


class RideHailingAllocationEngine(VehicleAllocationEngineInterface):
    __slots__ = (
        "_env",
        "_vehicles_assigned_to_users",
        "_vehicle_assignment_requests",
        "_vehicle_assignment_ids",
    )

    def __init__(self, env):
        self._env = env
        self._vehicles_assigned_to_users = self._env.event()
        self._env.process(self.run())
        self._vehicle_assignment_requests = []
        self._vehicle_assignment_ids = set()

    def run(self):
        while True:
            yield self._env.timeout(1)

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
            self._vehicle_assignment_ids.clear()

    def request_vehicle_allocation(
        self,
        user: RideHailingUser,
        selected_transportation_alternative: TransportationAlternative,
    ) -> VehicleAllocation:
        """
            Assign vehicle in transportation alternative to user
        :param user:
        :param selected_transportation_alternative:
        :return:
        """

        try:
            self._add_request(user, selected_transportation_alternative)
        except Exception:
            logging.error(
                f"Vehicle {selected_transportation_alternative.vehicle.id} already assigned to user {selected_transportation_alternative.vehicle.reserved_for_user.id}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

        yield self._vehicles_assigned_to_users

        selected_vehicle = selected_transportation_alternative.vehicle

        # No Vehicle Allocation
        if selected_vehicle.reserved_for_user != user:
            # print(selected_vehicle.reserved_for_user, user)
            return None

        # Vehicle was successfully allocated
        return VehicleAllocation(
            user,
            selected_vehicle,
            selected_transportation_alternative,
            selected_vehicle.position,
            selected_transportation_alternative.pick_up_time,
        )

    def notify_user_arrival_at_pick_up_position(
        self, vehicle_assignment: VehicleAllocation
    ):
        pass

        # For Autonomous Vehicles or Mass Transit (i.e., listen to position of vehicle)
        # old_position = vehicle_assignment.vehicle.position
        # from simulation.environment.geodesic_position import GeodesicPosition
        # vehicle_assignment.vehicle.position = GeodesicPosition(65.3, 13.3)
        # self._env.process(self.test(vehicle_assignment, old_position))

    def _add_request(self, user, vehicle_assignment):
        if vehicle_assignment.vehicle.id not in self._vehicle_assignment_ids:
            self._vehicle_assignment_requests.append((user, vehicle_assignment))
            self._vehicle_assignment_ids.add(vehicle_assignment.vehicle.id)
        else:
            raise Exception

    def test(self, vehicle_assignment, old_position):
        # Notify operator that user has arrived at location

        # self._env.process()
        yield self._env.timeout(10)

        from simulation.environment.geodesic_position import GeodesicPosition

        vehicle_assignment.vehicle.position = GeodesicPosition(55.3, 13.3)

        yield self._env.timeout(10)

        vehicle_assignment.vehicle.position = old_position
