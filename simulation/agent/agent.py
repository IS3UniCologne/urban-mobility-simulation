from abc import ABC, abstractmethod
from beartype import beartype
from typing import Any

from simulation.environment.position import Position


class Agent(ABC):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @property
    def state(self) -> Any:
        return self._state

    @state.setter
    @beartype
    def state(self, state: Any) -> None:
        self._state = state

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    @beartype
    def position(self, position: Position) -> None:
        self._position = position

    @abstractmethod
    def __str__(self) -> str:
        pass
