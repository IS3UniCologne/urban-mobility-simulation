import logging
from random import random

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
        yield self._auction.open_for_bidding
        # timeslots are denoted by their start time and have length `self._config.shared_charging_config.timeslot_duration`
        auctioned_timeslot = self._auction.next_timeslot
        auctioned_capacity = self._auction.get_auctioned_capacity()
        logging.debug(
            "Auction opened for timeslot %s",
            auctioned_timeslot,
            extra={
                "clazz": self.__class__.__name__,
                "oid": self._auction_participant_id,
            },
        )

        # TODO: implement real bid logic
        bid = {
            k: (v, random(), self._auction_participant_id)
            for k, v in auctioned_capacity.items()
        }

        self._auction.place_bid(bid)
        self.bidding_done.succeed()
        self.bidding_done = self._env.event()
        logging.debug(
            "Bids placed for timeslot %s",
            auctioned_timeslot,
            extra={
                "clazz": self.__class__.__name__,
                "oid": self._auction_participant_id,
            },
        )

        result = yield self.result_announced
        self.result_announced = self._env.event()
        logging.debug(
            "Results received for timeslot %s",
            auctioned_timeslot,
            extra={
                "clazz": self.__class__.__name__,
                "oid": self._auction_participant_id,
            },
        )

        self._virtual_charging_infrastructure.update(
            auctioned_timeslot, {k: v[0] for k, v in result.items()}
        )

    def _charge_vehicles(self):
        # TODO: this can use most of the ridehailing_charging_operations.py logic, but must work on to the capacity view instead of raw infrastructure
        pass
