from abc import ABC, abstractmethod  # noqa: D100


class PassengerInterface(ABC):  # noqa: D101
    @abstractmethod
    def mount_vehicle(self, vehicle):  # noqa: ANN001, ANN201, D102
        pass

    @abstractmethod
    def unmount_vehicle(self, vehicle):  # noqa: ANN001, ANN201, D102
        pass

    @abstractmethod
    def identify_passenger(self):  # noqa: ANN201, D102
        pass
