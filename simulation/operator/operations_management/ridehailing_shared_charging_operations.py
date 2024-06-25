from simpy import Environment

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.world.markets.auction import Auction
from simulation.world.markets.interfaces.bidder_interface import BidderInterface


class RideHailingSharedChargingOperations(OperationsInterface, BidderInterface):
    def __init__(self, env: Environment, auction: Auction):
        super().__init__(env)

        self._auction = auction
        self._auction_participant_id = self._auction.register_participant(self)
        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None

    def execute(self):
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            self._env, self._operator_reference.charging_infrastructure
        )
        while True:
            # this operator has two jobs to do:
            # 1) bid for capacity
            # 2) charge vehicles

            self._env.process(self._bid_for_capacity())
            self._env.process(self._charge_vehicles())

    def _bid_for_capacity(self):
        yield self._auction.open_for_bidding
        # timeslots are denoted by their start time and have length `self._config.shared_charging_config.timeslot_duration`
        auctioned_timeslot = self._auction.next_timeslot()

        # TODO: implement bid logic
        bid = {"871f1d4c9ffffff": (2, 0.1, self._auction_participant_id)}

        self._auction.place_bid(bid)

        result = yield self.result_announced

        self._virtual_charging_infrastructure.update(auctioned_timeslot, result)

    def _charge_vehicles(self):
        # TODO: this can use most of the ridehailing_charging_operations.py logic, but must work on to the virtual charging infrastructure view instead of raw infrastructure
        yield self._env.timeout(1)
