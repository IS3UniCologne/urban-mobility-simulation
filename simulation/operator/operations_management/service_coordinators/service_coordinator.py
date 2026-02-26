from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simpy import Event

    from simulation.context.simulation_context import SimulationContext


class ServiceCoordinator(ABC, SimulationBase):
    """Base class for service coordinators.

    Service coordinators orchestrate operational service tasks.
    """

    __slots__ = ("_env", "_sim", "_start_time", "_task_finished")

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._sim = sim
        self._env = sim.env
        self._start_time = self._env.now
        self._task_finished = self._env.event()

    @abstractmethod
    def execute(self) -> None:  # noqa: D102
        pass

    @property
    def task_finished(self) -> Event:  # noqa: D102
        return self._task_finished
