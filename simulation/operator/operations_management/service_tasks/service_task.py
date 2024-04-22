from abc import ABC, abstractmethod

from simpy import Environment


class ServiceTask(ABC):
    def __init__(self, env: Environment):
        self._env = env
        self._task_finished = self._env.event()

    @abstractmethod
    def execute(self, *args):
        pass

    @property
    def task_finished(self):
        return self._task_finished
