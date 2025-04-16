from abc import ABC, abstractmethod
from typing import Tuple, Any
from beartype import beartype


class Position(ABC):
    @abstractmethod
    def __init__(self) -> None:
        self._x: str = "I have a x position"
        self._y: str = "I have a y position"

    @abstractmethod
    @beartype
    def getExactLocation(self) -> Tuple[float, float]:
        pass

    @abstractmethod
    def __str__(self) -> str:
        pass
