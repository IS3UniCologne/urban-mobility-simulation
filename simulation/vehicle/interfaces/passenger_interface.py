from abc import ABC, abstractmethod


class PassengerInterface(ABC):

    @abstractmethod
    def mount_vehicle(self, vehicle):
        pass

    @abstractmethod
    def unmount_vehicle(self, vehicle):
        pass

    @abstractmethod
    def identify_passenger(self):
        pass
