from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition


class Agent(SimulationBase, ABC):  # noqa: D101
    __slots__ = ("_position", "_state")

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)

    @property
    def state(self):  # noqa: ANN201, D102
        return self._state

    @state.setter
    def state(self, state) -> None:  # noqa: ANN001
        self._state = state

    @property
    def position(self) -> GeodesicPosition:  # noqa: D102
        return self._position

    @position.setter
    def position(self, position: GeodesicPosition) -> None:
        self._position = position

    @abstractmethod
    def __str__(self) -> str:  # noqa: D105
        pass
        pass
