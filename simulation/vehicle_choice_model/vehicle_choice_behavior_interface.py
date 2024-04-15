from abc import ABC, abstractmethod
from typing import Dict

from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics


class VehicleChoiceBehaviorInterface(ABC):
    @abstractmethod
    def choose_vehicle(
        self, trip_characteristics: TripCharacteristics
    ) -> Dict[str, int]:
        pass
