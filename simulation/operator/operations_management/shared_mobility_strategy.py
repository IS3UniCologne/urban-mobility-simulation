from simpy import Environment

from simulation.operator.interface.service_workforce_interface import (
    ServiceWorkforceInterface,
)
from simulation.operator.service_workforce import ServiceWorkforce


class SharedMobiltyStrategy(ServiceWorkforceInterface):
    def __init__(self, env: Environment):
        self._env = env

    def register_workforce(self, workforce: ServiceWorkforce):
        self._service_workforce = workforce
