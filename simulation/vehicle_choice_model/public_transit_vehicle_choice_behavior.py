from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics  # noqa: D100
from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import (
    VehicleChoiceBehaviorInterface,
)


class PublicTransitVehicleChoiceBehavior(VehicleChoiceBehaviorInterface):
    """
    Currently, this is only a dummy class that emulates Vehicle Choice Behavior in the absence of choice
    """  # noqa: D200, D400

    __slots__ = ("_available_modes",)

    def __init__(self, available_modes):  # noqa: ANN001, ANN204
        self._available_modes = available_modes

    def choose_vehicle(self, trip_characteristics: TripCharacteristics):  # noqa: ANN201, D102
        # return the only known PublicTransit Mode: Bus as the viable "choice"
        return {self._available_modes[0]: 1}
