from simpy import Environment

from simulation.operator.interface.relocation_interface import RelocationInterface
from simulation.operator.vehicle_fleet import VehicleFleet


class RelocationStrategy(RelocationInterface):

    def __init__(self, env: Environment):
        self._env = env

    def relocate_fleet(self, fleet: VehicleFleet):
        raise NotImplementedError('This is the base class, your implementation of a relocation strategy should overwrite this method!')