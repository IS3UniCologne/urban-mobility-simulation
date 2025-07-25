from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NewType

# RegionId represents a unique identifier for a spatial region (e.g., an H3 hex ID).
RegionId = NewType("RegionId", str)


class Position(ABC):
    @abstractmethod
    def getExactLocation(self) -> tuple[float, float]:
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
    def __rshift__(self, other: Position) -> float:
        # Calculate distance between two positions
        pass
