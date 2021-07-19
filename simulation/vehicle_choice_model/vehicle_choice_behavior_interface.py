from abc import abstractmethod, ABC

from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics

class VehicleChoiceBehaviorInterface(ABC):

    @abstractmethod
    def choose_vehicle(self, trip_characteristics: TripCharacteristics):
        pass
