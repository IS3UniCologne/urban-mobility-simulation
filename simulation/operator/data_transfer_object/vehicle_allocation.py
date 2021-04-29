from simulation.environment.position import Position
from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.vehicle.vehicle import Vehicle

class VehicleAllocation:
    def __init__(self, user, vehicle: Vehicle, associated_transportation_alternative: TransportationAlternative, pick_up_position: Position, pick_up_time = 0):
        self._user                   = user                                     # User that got the assignment
        self._vehicle                = vehicle                                  # Vehicle that got assigned to above user
        self._associated_alternative = associated_transportation_alternative    # Selected transportation offer
        self._pick_up_position       = pick_up_position                         # Pick up position of user for vehicle
        self._pick_up_time           = pick_up_time                             #  Pick up time (i.e., when will be the vehicle be at pickup pos)


    @property
    def user(self):
        return self._user

    @property
    def vehicle(self):
        return self._vehicle

    @property
    def associated_transportation_alternative(self):
        return self._associated_alternative

    @property
    def pick_up_position(self):
        return self._pick_up_position

    @property
    def pick_up_time(self):
        return self._pick_up_time