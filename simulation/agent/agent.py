from abc import ABC, abstractmethod

from simulation.environment.position import Position


class Agent(ABC):
    __slots__ = ("_position", "_state")

    @abstractmethod
    def __init__(self) -> None:
        pass

    @property
    def state(self):  # noqa: ANN201
        return self._state

    @state.setter
    
    def state(self, state) -> None:  # noqa: ANN001
        self._state = state

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    
    def position(self, position: Position) -> None:
        self._position = position

    @abstractmethod
    def __str__(self) -> str:
        pass
