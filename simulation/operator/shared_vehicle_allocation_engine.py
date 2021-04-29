from simulation.agent.user import User
from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.operator.data_transfer_object.vehicle_allocation import VehicleAllocation
from simulation.operator.interface.vehicle_allocation_engine_interface import VehicleAllocationEngineInterface


class SharedVehicleAllocationEngine(VehicleAllocationEngineInterface):

    def __init__(self, env):
        self._env = env
        self._vehicles_assigned_to_users = self._env.event()
        self._env.process(self.run())
        self._vehicle_assignment_requests = []

    def run(self):
        while True:
            yield self._env.timeout(45)
            # Implement vehicle assignment functionality here
            self._vehicles_assigned_to_users.succeed()
            self._vehicles_assigned_to_users = self._env.event()
            self._vehicle_assignment_requests.clear()


    def request_vehicle_allocation(self, user: User, selected_transportation_alternative: TransportationAlternative) -> VehicleAllocation:
        """
            Assign vehicle in transportation alternative to user
        :param user:
        :param selected_transportation_alternative:
        :return:
        """

        self._vehicle_assignment_requests.append(selected_transportation_alternative)

        yield self._vehicles_assigned_to_users

        selected_vehicle = selected_transportation_alternative.vehicle

        return VehicleAllocation(user, selected_vehicle, selected_transportation_alternative, selected_vehicle.position)

    def notify_user_arrival_at_pick_up_position(self, vehicle_assignment: VehicleAllocation):
        # Notify operator that user has arrived at location
        return