from simpy import Environment

from simulation.operator.interface.refueling_interface import RefuelingInterface
from simulation.operator.vehicle_fleet import VehicleFleet


class RefuelingStrategy(RefuelingInterface):
    def __init__(self, env: Environment):
        self._env = env

    def refuel_fleet(self, fleet: VehicleFleet):
        raise NotImplementedError(
            "This is the base class, your implementation of a refueling strategy should overwrite this method!"
        )
