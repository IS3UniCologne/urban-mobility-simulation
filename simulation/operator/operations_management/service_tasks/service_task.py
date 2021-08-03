from abc import ABC, abstractmethod


class ServiceTask(ABC):

    @abstractmethod
    def execute(self, simpy_env, *args):
        pass