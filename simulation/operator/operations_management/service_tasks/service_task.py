from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import TaskState, TaskType
from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simpy import Event

    from simulation.context.simulation_context import SimulationContext


class ServiceTask(ABC, SimulationBase):  # noqa: D101
    __slots__ = (
        "_end_time",
        "_env",
        "_sim",
        "_start_time",
        "_state",
        "_task_finished",
        "_task_type",
    )

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._sim = sim
        self._env = sim.env
        self._task_type = TaskType.SERVICE
        self._start_time = self._env.now
        self._end_time = None
        self._state: TaskState = TaskState.INITIALIZED
        self._task_finished = self._env.event()

    @abstractmethod
    def execute(self) -> None:  # noqa: D102
        pass

    @property
    def state(self) -> TaskState:  # noqa: D102
        return self._state

    @property
    def start_time(self) -> float:  # noqa: D102
        return self._start_time

    @property
    def end_time(self) -> float | None:  # noqa: D102
        return self._end_time

    @property
    def task_finished(self) -> Event:  # noqa: D102
        return self._task_finished

    @property
    def task_type(self) -> TaskType:  # noqa: D102
        return self._task_type
