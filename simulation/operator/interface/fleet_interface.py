from abc import ABC, abstractmethod

import simpy
from simpy import Environment


class FleetInterface(ABC):
    def __init__(self, env: Environment):
        self._resource = simpy.Resource(env)  # Semaphore

    @property
    def resource(self):
        """
        SimPy Resource to handle parallel accessd
        :return:
        """
        return self._resource

    @abstractmethod
    def get_all_vehicles(self, region):
        pass

    @abstractmethod
    def get_available_vehicles(self, region):
        pass
