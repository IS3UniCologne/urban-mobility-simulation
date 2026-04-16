from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.helper.types import RegionId


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
