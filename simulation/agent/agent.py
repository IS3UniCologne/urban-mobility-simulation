from abc import ABC, abstractmethod

from simulation.environment.position import Position
from simulation.helper.simulation_base import SimulationBase


class Agent(SimulationBase, ABC):
    __slots__ = ("_position", "_state")

    def __init__(self) -> None:
        super().__init__()

    @property
    def state(self):  # noqa: ANN201
        return self._state

    @state.setter
    def state(self, state):  # noqa: ANN001, ANN202
        self._state = state

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, position: Position):  # noqa: ANN202
        self._position = position

    @abstractmethod
    def __str__(self):  # noqa: ANN204
        pass
