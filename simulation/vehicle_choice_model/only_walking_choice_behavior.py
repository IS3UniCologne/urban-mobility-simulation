from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics
from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import (
    VehicleChoiceBehaviorInterface,
)


# TODO: Do we want to keep this ?
class OnlyWalkingChoiceBehavior(VehicleChoiceBehaviorInterface):
    """
    The only choice in this behavior is to walk
    """

    def __init__(self, available_modes):
        self._available_modes = available_modes

    def choose_vehicle(self, trip_characteristics: TripCharacteristics):
        result = {self._available_modes[0]: 1}
        return result
