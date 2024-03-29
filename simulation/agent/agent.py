from abc import ABC, abstractmethod

from simulation.environment.position import Position


class Agent(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, position: Position):
        self._position = position

    @abstractmethod
    def __str__(self):
        pass
