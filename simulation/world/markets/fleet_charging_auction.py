from typing import Dict, Tuple

from simpy import Environment

from simulation.world.markets.auction import Auction
from simulation.world.markets.interfaces.bidder_interface import BidderInterface


class FleetChargingAuction(Auction):
    __slots__ = ("_participants", "_charging_locations", "_next_timeslot")

    # bids are n>=0 tuples of (integer, float, int)[number, bid price, bidder id] PER charging station, charging stations are denoted by h3hex ID (str)
    __bid_syntax = Dict(str, Tuple(int, float, int))
    # results are n=1 tuples of (integer, float)[number, clearing price] PER charging station, PER participant, charging stations are denoted by h3hex ID (str)
    __result_syntax = Dict(str, Dict(int, Tuple(int, float)))

    def __init__(self, env: Environment, start_condition, end_condition) -> None:
        super().__init__(env, start_condition, end_condition)
        self._participants = []
        self._charging_locations = []
        self._next_timeslot = self._config.auction_config.auction_start

    def run(self) -> None:
        while True:
            if self._env.now() < self._next_timeslot:
                yield self._env.timeout(self._next_timeslot - self._env.now)

            self._is_open = True
            self.open_for_bidding.succeed()

            # wait for bids?

            self._clear()
            self._announce_results()

            self._next_timeslot = (
                self._next_timeslot + self._config.auction_config.auction_interval
            )
            self._is_open = False

    def register_participant(self, participant: BidderInterface) -> None:
        self._participants.append(participant)

    def _clear(self) -> None:
        for c in self._charging_locations:
            self._clear_single(c)

    def _clear_single(self, charging_location: int) -> None:
        location_bids = self._bids[charging_location]

        # TODO: clear using uniform pricing
        location_result = None

        self._result[charging_location] = location_result

    def _announce_results(self) -> None:
        for p in self._participants:
            p.result_announced.succeed(self._result[p])

    @property
    def result(self):
        # it is illegal for other participants to know the full results in this type of auction
        raise NotImplementedError(
            "Not implemented for FleetChargingAuction, results are distributed through events"
        )
