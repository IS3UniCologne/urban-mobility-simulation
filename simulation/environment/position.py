from abc import ABC, abstractmethod


class Position(ABC):
    __slots__ = ("_x", "_y")

    @abstractmethod
    def __init__(self):  # noqa: ANN204
        self._x = "I have a x position"
        self._y = "I have a y position"

    @abstractmethod
    def getExactLocation(self):  # noqa: ANN201
        pass

    @abstractmethod
    def __str__(self):  # noqa: ANN204
        pass

    @abstractmethod
    def get_region_id(self) -> str:
        """
        Get the region ID of the position
        :return: str
        """
        pass

    @abstractmethod
    def __rshift__(self, other) -> float:  # noqa: ANN001
        # Calculate distance between two positions
        pass
