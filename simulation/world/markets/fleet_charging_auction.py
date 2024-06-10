from typing import Tuple

from simpy import Environment

from simulation.world.markets.auction import Auction


class FleetChargingAuction(Auction):
    __slots__ = ("_participants",)

    __bid_syntax = Tuple(int, float, int)
    __result_syntax = Tuple(int, float)

    def __init__(self, env: Environment, start_condition, end_condition) -> None:
        super().__init__(env, start_condition, end_condition)
        self._participants = []

    def register_participant(self, participant: BidderInterface) -> None:
        self._participants.append(participant)
