from __future__ import annotations  # noqa: D100

import dataclasses
from collections import namedtuple
from typing import TYPE_CHECKING

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.algorithms.distance_based_bidding_strategy import (
    get_bid,
)
from simulation.operator.operations_management.ride_hailing_operations import (
    RideHailingOperations,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.world.markets.interfaces.bidder_interface import BidderInterface

if TYPE_CHECKING:
    from simulation.operator.operations_management.operations import (
        OperationsDependencies,
    )


class RideHailingSharedChargingOperations(RideHailingOperations, BidderInterface):  # noqa: D101
    __slots__ = (
        "_auction",
        "_bidding_parameters",
        "_charging_operations",
        "_config",
        "_deps",
        "_distance_matrix",
        "_operations_config",
        "_sim",
        "_state_of_charge_threshold",
        "_virtual_charging_infrastructure",
        "_world",
    )

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)

        self._deps = deps

        self._auction = self._operator.charging_infrastructure.auction

        BidderInterface.__init__(self, env=self._env, auction=self._auction)

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        # self._bidding_strategy = bidding_strategy
        self._state_of_charge_threshold = self._config.RECHARGE_THRESHOLD
        self._charging_operations = None

    def execute(self):  # noqa: ANN201, D102
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            sim=self._sim,
            charging_infrastructure=self._operator.charging_infrastructure,
            lookahead=self._auction._shared_charging_config.AUCTION_LOOKAHEAD,  # noqa: SLF001
        )

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["id", "fleet", "charging_infrastructure"]
        )

        # TODO: can we just use uid instead ?
        id = self._operator.uid.split("_")[1]
        vo = VirtualOperator(
            id=id,
            fleet=self._operator.fleet,
            charging_infrastructure=self._virtual_charging_infrastructure,
        )

        patched_deps = dataclasses.replace(
            self._deps, operator=vo
        )  # shallow copy, as we want to retain references to sim and world

        self._charging_operations = RideHailingBaseChargingOperations(patched_deps)

        self._env.process(self._delay_charging_operations())

        while True:
            # this operator has two jobs to do:
            # 1) bid for capacity
            # 2) charge vehicles - done by self._charging_operations

            yield self._env.process(self._bid_for_capacity())

    def _bid_for_capacity(self):  # noqa: ANN202
        yield self._auction.open_for_bidding
        # timeslots are denoted by their start time and have length `self._config.shared_charging_auction.TIMESLOT_DURATION`
        auctioned_timeslot = self._auction.next_timeslot
        auctioned_capacity = self._auction.get_auctioned_capacity()
        self.logger.debug("Auction opened for timeslot %s", auctioned_timeslot)

        # TODO: refactor to be a method of somethign like "BiddingStrategy"
        # TODO: right now we track bids through the auction, maybe we can use transactions for that?
        self._bids = get_bid(
            auctioned_timeslot=auctioned_timeslot,
            auctioned_capacity=auctioned_capacity,
            bid_decay=self._config.BID_DECAY,
            random_overbidding=self._config.RANDOM_OVERBIDDING,
            overbid_prob=self._config.OVERBID_PROB,
            bid_default=self._config.BID_DEFAULT,
            operator_reference=self._operator,
            state_of_charge_threshold=self._state_of_charge_threshold,
            participant_id=self._auction_participant_id,
            distance_matrix=self._distance_matrix,
        )
        # {
        #   k: [(v, random(), self._auction_participant_id)]
        #    for k, v in auctioned_capacity.items()
        # }
        # self._bidding_strategy.get_bid(auctioned_timeslot, auctioned_capacity)

        if self._bids:
            self._auction.place_bid(self._bids)

        self.bidding_done.succeed()
        self.bidding_done = self._env.event()
        self.logger.debug("Bids placed for timeslot %s", auctioned_timeslot)

        self._result = yield self.result_announced
        self.result_announced = self._env.event()
        self.logger.debug("Results received for timeslot %s", auctioned_timeslot)

        self._virtual_charging_infrastructure.update(
            availability={k: v[0] for k, v in self._result.items()},
            timeslot=auctioned_timeslot,
        )

    def _delay_charging_operations(self):  # noqa: ANN202
        # Logic: Wait until t=1 because we start auctions at t=0+(auction_interval) and then the charging operations process can run in intervals of auction_interval, this works because the auction is instant from simulation-time perspective

        yield self._env.timeout(1)
        self._env.process(self._charging_operations.execute())

    @property
    def task_transactions(self):  # noqa: ANN201, D102
        return self._charging_operations.task_transactions
