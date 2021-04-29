from abc import ABC, abstractmethod

class DriverInterface(ABC):

    @abstractmethod
    def mount_vehicle_as_driver(self, vehicle):
        pass

    @abstractmethod
    def unmount_vehicle_as_driver(self, vehicle):
        pass

    @abstractmethod
    def drive_vehicle(self, vehicle, route):
        pass

    @abstractmethod
    def park_vehicle(self, vehicle, position = None):
        pass

    @abstractmethod
    def identify_driver(self):
        pass