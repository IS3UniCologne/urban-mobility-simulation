from __future__ import annotations  # noqa: D100

import dataclasses
from collections import namedtuple
from typing import TYPE_CHECKING
from simulation.helper.configuration.configuration import ChargingStrategy

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.algorithms.distance_based_bidding_strategy import HeuristicStrategy

from simulation.operator.operations_management.RLBiddingConnector import RLStrategy

from simulation.operator.operations_management.ride_hailing_operations import (
    RideHailingOperations,
)
from simulation.operator.operations_management.ridehailing_greedy_charging_operations import (
    RideHailingGreedyChargingOperations,
)
from simulation.operator.operations_management.ridehailing_explicit_charging_operations import (
    RideHailingExplicitChargingOperations
)
from simulation.world.markets.interfaces.bidder_interface import BidderInterface

if TYPE_CHECKING:
    import pandas as pd

    from simulation.operator.operations_management.operations import (
        OperationsDependencies,
    )


class RideHailingSharedChargingOperations(RideHailingOperations, BidderInterface):  # noqa: D101
    __slots__ = (
        "_auction",
        "_bidding_parameters",
        "_bidding_strategy"
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

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure | None = (
            None
        )

        if(self._config.STRATEGY == ChargingStrategy.RL):
            self._bidding_strategy = RLStrategy(self._sim.env, self._operator, self._auction)
        else:
            self._bidding_strategy = HeuristicStrategy(self._sim.env, self._operator, self._auction)

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
            "VirtualOperator", ["fleet", "charging_infrastructure"]
        )

        virtual_operator = VirtualOperator(
            fleet=self._operator.fleet,
            charging_infrastructure=self._virtual_charging_infrastructure,
        )

        patched_deps = dataclasses.replace(
            self._deps, operator=virtual_operator
        )  # shallow copy, as we want to retain references to sim and world

        if(self._config.STRATEGY == ChargingStrategy.RL):
            #self._bidding_strategy = RideHailingExplicitChargingOperations()
            self._charging_operations = RideHailingExplicitChargingOperations(patched_deps)
        else:
            self._charging_operations = RideHailingGreedyChargingOperations(patched_deps)

        self._env.process(self._delay_charging_operations())

        while True:
            # this operator has two jobs to do:
            # 1) bid for capacity
            # 2) charge vehicles - done by self._charging_operations

            yield self._env.process(self._bid_for_capacity())

    def _bid_for_capacity(self):  # noqa: ANN202
        #yield self._auction.open_for_bidding
        # timeslots are denoted by their start time and have length `self._config.shared_charging_auction.TIMESLOT_DURATION`
        auctioned_timeslot = self._auction.next_timeslot
        auctioned_capacity = self._auction.get_auctioned_capacity()
        self.logger.debug("Auction opened for timeslot %s", auctioned_timeslot)

        self._bids = yield self._env.process(
            self._bidding_strategy.get_bids(self, auctioned_timeslot, auctioned_capacity)
        )

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

    def _delay_charging_operations(self):
        # Wait until the initial setup buffer passes
        yield self._env.timeout(1)
        
        interval = self._auction._shared_charging_config.AUCTION_INTERVAL
        
        while True:
            # Run a sweep of the greedy charging operations logic
            pairs = {}

            for cs_location, result_tuple in self._result.items():
                won_capacity, clearing_price = result_tuple[0], result_tuple[1]
                
                # 1. Skip if this station allocated no capacity to this operator
                if won_capacity <= 0:
                    continue
                    
                # 2. Get the bids for this location
                location_bids = self.bids.get(cs_location, [])
                
                # 3. Sort bids descending by price (bid[1]) to match auction logic
                sorted_bids = sorted(location_bids, key=lambda x: x[1], reverse=True)
                
                # 4. Take only the top 'won_capacity' number of bids
                winning_bids = sorted_bids[:won_capacity]
                
                # 5. Map the vehicle_id or bidder_id to the location
                for bid in winning_bids:
                    # NOTE: earlier you mentioned vehicle_id is at index 3: bid[3]
                    # If it's the last item, use bid[3]. If it's the 3rd, use bid[2].
                    vehicle_id = bid[3] 
                    pairs[vehicle_id] = cs_location
                    
            # FIX: Ensure you pass the expected signature parameters to execute()
            yield self._env.process(self._charging_operations.execute(pairs))
            
            # Wait for the next interval before sweeping the fleet again
            yield self._env.timeout(interval)

    @property
    def job_transactions(self) -> pd.DataFrame:  # noqa: D102
        return self._charging_operations.job_transactions

    @property
    def bids(self):  # noqa: D102
        return self._bids

    @property
    def bidding_strategy(self):  # noqa: D102
        return self._bidding_strategy
