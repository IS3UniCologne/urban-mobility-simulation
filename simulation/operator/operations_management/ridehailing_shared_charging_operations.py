from simpy import Environment

from simulation.operator.operations_management.operations import OperationsInterface
from simulation.world.markets.auction import Auction


class RideHailingSharedChargingOperations(OperationsInterface):
    def __init__(self, env: Environment, auction: Auction):
        super().__init__(env)

        self._auction = auction

    def execute(self):
        # this operator has two jobs to do:
        # 1) bid for capacity
        # 2) charge vehicles

        self._env.process(self._bid_for_capacity())
        self._env.process(self._charge_vehicles())

    def _bid_for_capacity(self):
        yield self._auction.started

        # TODO: implement bid logic
        pass

    def _charge_vehicles(self):
        # TODO: this can use most of the ridehailing_charging_operations.py logic, but must work on to the capacity view instead of raw infrastructure
        pass
