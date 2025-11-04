from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import NewType

# RegionId represents a unique identifier for a spatial region (e.g., an H3 hex ID).
RegionId = NewType("RegionId", str)


class Position(ABC):  # noqa: D101
    @abstractmethod
    def getExactLocation(self) -> tuple[float, float]:  # noqa: D102
        pass

    @abstractmethod
    def __str__(self) -> str:  # noqa: D105
        pass

    @abstractmethod
    def get_region_id(self) -> RegionId:
        """
        Get the region ID of the position
        :return: RegionId
        """  # noqa: D205, D400
        pass

    @abstractmethod
    def __rshift__(self, other: Position) -> float:  # noqa: D105
        # Calculate distance between two positions
        pass
