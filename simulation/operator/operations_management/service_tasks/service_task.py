from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simpy import Event

    from simulation.context.simulation_context import SimulationContext


class TaskState(Enum):
    INITIALIZED = 0
    EXECUTING = 10
    EXECUTING_RELOCATION = 11
    EXECUTING_WAITING = 12
    EXECUTING_CHARGING = 13
    FINISHED = 20
    MISSED = 30
    MISSED_TIMESLOT = 31
    MISSED_QUEUE_FULL = 32


class ServiceTask(ABC, SimulationBase):
    __slots__ = ("_env", "_sim", "_start_time", "_state", "_task_finished")

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._sim = sim
        self._env = sim.env
        self._start_time = self._env.now
        self._state: TaskState = TaskState.INITIALIZED
        self._task_finished = self._env.event()

    @abstractmethod
    def execute(self) -> None:
        pass

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def task_finished(self) -> Event:
        return self._task_finished
