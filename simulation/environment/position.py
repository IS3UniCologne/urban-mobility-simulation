from abc import ABC, abstractmethod
from typing import NewType

# RegionId represents a unique identifier for a spatial region (e.g., an H3 hex ID).
RegionId = NewType("RegionId", str)
from typing import Tuple, Any
from beartype import beartype


class Position(ABC):
    __slots__ = ("_x", "_y")

    @abstractmethod
    def __init__(self) -> None:  # noqa: ANN204
        self._x: str = "I have a x position"
        self._y: str = "I have a y position"

    @abstractmethod
    @beartype
    def getExactLocation(self) -> Tuple[float, float]:  # noqa: ANN201
        pass

    @abstractmethod
    def __str__(self) -> str:
        pass

    @abstractmethod
    def get_region_id(self) -> RegionId:
        """
        Get the region ID of the position
        :return: RegionId
        """
        pass

    @abstractmethod
    def __rshift__(self, other) -> float:  # noqa: ANN001
        # Calculate distance between two positions
        pass
