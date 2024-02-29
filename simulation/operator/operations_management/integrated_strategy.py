from simpy import Environment

from simulation.operator.interface.refueling_interface import RefuelingInterface
from simulation.operator.interface.relocation_interface import RelocationInterface
from simulation.operator.vehicle_fleet import VehicleFleet

class IntegratedStrategy(RefuelingInterface, RelocationInterface):

    def __init__(self, env: Environment):
        self._env = env

    def refuel_fleet(self, fleet: VehicleFleet):
        raise NotImplementedError('This is the base class, your implementation of a refueling strategy should overwrite this method!')

    def relocate_fleet(self, fleet: VehicleFleet):
        raise NotImplementedError('This is the base class, your implementation of a relocation strategy should overwrite this method!')
    