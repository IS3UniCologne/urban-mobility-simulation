from random import random

from simpy import Environment

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.world.markets.auction import Auction
from simulation.world.markets.interfaces.bidder_interface import BidderInterface


class RideHailingSharedChargingOperations(OperationsInterface, BidderInterface):
    def __init__(self, env: Environment, auction: Auction):
        OperationsInterface.__init__(self, env)
        BidderInterface.__init__(self, env, auction)

        self._auction_participant_id = self._auction.register_participant(self)
        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None

    @property
    def auction_participant_id(self):
        return self._auction_participant_id

    def execute(self):
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            self._env, self._operator_reference.charging_infrastructure
        )
        while True:
            # this operator has two jobs to do:
            # 1) bid for capacity
            # 2) charge vehicles

            yield self._env.process(self._bid_for_capacity())
            yield self._env.process(self._charge_vehicles())

    def _bid_for_capacity(self):
        yield self._auction.open_for_bidding
        # timeslots are denoted by their start time and have length `self._config.shared_charging_config.timeslot_duration`
        auctioned_timeslot = self._auction.next_timeslot
        auctioned_capacity = self._auction.get_auctioned_capacity()

        # TODO: implement real bid logic
        bid = {
            k: (v, random(), self._auction_participant_id)
            for k, v in auctioned_capacity.items()
        }

        self._auction.place_bid(bid)
        self.bidding_done.succeed()
        self.bidding_done = self._env.event()

        result = yield self.result_announced
        self.result_announced = self._env.event()

        self._virtual_charging_infrastructure.update(
            auctioned_timeslot, {k: v[0] for k, v in result.items()}
        )

    def _charge_vehicles(self):
        # TODO: this can use most of the ridehailing_charging_operations.py logic, but must work on to the virtual charging infrastructure view instead of raw infrastructure
        yield self._env.timeout(1)
