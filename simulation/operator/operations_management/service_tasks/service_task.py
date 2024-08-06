from abc import ABC, abstractmethod
from enum import Enum

from simpy import Environment


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


class ServiceTask(ABC):
    __slots__ = ("_env", "_start_time", "_state", "_task_finished")

    def __init__(self, env: Environment):
        self._env = env
        self._start_time = self._env.now
        self._state: TaskState = TaskState.INITIALIZED
        self._task_finished = self._env.event()

    @abstractmethod
    def execute(self):
        pass

    @property
    def state(self):
        return self._state

    @property
    def task_finished(self):
        return self._task_finished
