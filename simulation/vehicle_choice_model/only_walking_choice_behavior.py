from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics
from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import (
    VehicleChoiceBehaviorInterface,
)


class OnlyWalkingChoiceBehavior(VehicleChoiceBehaviorInterface):
    """
    The only choice in this behavior is to walk
    """

    __slots__ = ("_available_modes",)

    def __init__(self, available_modes):  # noqa: ANN001, ANN204
        self._available_modes = available_modes

    def choose_vehicle(self, trip_characteristics: TripCharacteristics):  # noqa: ANN201
        result = {self._available_modes[0]: 1}
        return result
