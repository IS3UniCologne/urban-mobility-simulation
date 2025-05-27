from abc import ABC, abstractmethod


class DriverInterface(ABC):
    @abstractmethod
    def mount_vehicle_as_driver(self, vehicle):  # noqa: ANN001, ANN201
        pass

    @abstractmethod
    def unmount_vehicle_as_driver(self, vehicle):  # noqa: ANN001, ANN201
        pass

    @abstractmethod
    def drive_vehicle(self, vehicle, route):  # noqa: ANN001, ANN201
        pass

    @abstractmethod
    def park_vehicle(self, vehicle, position=None):  # noqa: ANN001, ANN201
        pass

    @abstractmethod
    def identify_driver(self):  # noqa: ANN201
        pass
