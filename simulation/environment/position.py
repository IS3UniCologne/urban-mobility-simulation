from abc import ABC, abstractmethod


class Position(ABC):
    __slots__ = ("_x", "_y")

    @abstractmethod
    def __init__(self):
        self._x = "I have a x position"
        self._y = "I have a y position"

    @abstractmethod
    def getExactLocation(self):
        pass

    @abstractmethod
    def __str__(self):
        pass

    @abstractmethod
    def get_region_id(self) -> str:
        """
        Get the region ID of the position
        :return: str
        """
        pass

    @abstractmethod
    def __rshift__(self, other) -> float:
        # Calculate distance between two positions
        pass
