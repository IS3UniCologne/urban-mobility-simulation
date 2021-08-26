from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import VehicleChoiceBehaviorInterface
from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics


class PublicTransitVehicleChoiceBehavior(VehicleChoiceBehaviorInterface):
    """
    Currently, this is only a dummy class that emulates Vehicle Choice Behavior in the absence of choice
    """
    def __init__(self, available_modes):
        self._available_modes = available_modes

    def choose_vehicle(self, trip_characteristics: TripCharacteristics):
        # return the only known PublicTransit Mode: Bus as the viable "choice"
        return {self._available_modes[0]: 1}
