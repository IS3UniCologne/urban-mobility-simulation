from abc import ABC, abstractmethod
from beartype import beartype
from typing import Any

from simulation.environment.position import Position


class Agent(ABC):
    __slots__ = ("_position", "_state")

    @abstractmethod
    def __init__(self) -> None:  # noqa: ANN204
        pass

    @property
    def state(self) -> Any:  # noqa: ANN201
        return self._state

    @state.setter
    @beartype
    def state(self, state: Any) -> None:  # noqa: ANN001, ANN202
        self._state = state

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    @beartype
    def position(self, position: Position) -> None:  # noqa: ANN202
        self._position = position

    @abstractmethod
    def __str__(self) -> str:  # noqa: ANN204
        pass
