from abc import ABC, abstractmethod  # noqa: D100

from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics


class VehicleChoiceBehaviorInterface(ABC):  # noqa: D101
    @abstractmethod
    def choose_vehicle(  # noqa: D102
        self, trip_characteristics: TripCharacteristics
    ) -> dict[str, int]:
        pass
