from __future__ import annotations

from collections import namedtuple
from typing import TYPE_CHECKING

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.interface.operations_interface import OperationsInterface
from simulation.operator.operations_management.algorithms.distance_based_bidding_strategy import (
    get_bid,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.world.markets.interfaces.bidder_interface import BidderInterface

if TYPE_CHECKING:
    import pandas as pd

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import OperationsConfig
    from simulation.operator.ride_hailing_operator import RideHailingOperator
    from simulation.world.world import World


class RideHailingSharedChargingOperations(BidderInterface, OperationsInterface):
    __slots__ = (
        "_auction",
        "_bidding_parameters",
        "_charging_operations",
        "_config",
        "_distance_matrix",
        "_operations_config",
        "_sim",
        "_state_of_charge_threshold",
        "_virtual_charging_infrastructure",
    )

    def __init__(  # noqa: ANN204
        self,
        sim: SimulationContext,
        distance_matrix: pd.DataFrame,
        operations_config: OperationsConfig,
        world: World,
        operator: RideHailingOperator,
    ):
        self._env = sim.env
        self._sim = sim
        self._operations_config = operations_config
        self._world = world
        self._auction = operator.charging_infrastructure.auction

        OperationsInterface.__init__(self, sim)
        BidderInterface.__init__(self, env=sim.env, auction=self._auction)

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        # self._bidding_strategy = bidding_strategy
        self._state_of_charge_threshold = operations_config.RECHARGE_THRESHOLD
        self._distance_matrix = distance_matrix
        self._config = sim.config
        self._charging_operations = None

    def execute(self):  # noqa: ANN201
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            sim=self._sim,
            charging_infrastructure=self._operator_reference.charging_infrastructure,
            lookahead=self._auction._shared_charging_config.AUCTION_LOOKAHEAD,  # noqa: SLF001
        )

        self._charging_operations = RideHailingBaseChargingOperations(
            sim=self._sim,
            operations_config=self._operations_config,
            distance_matrix=self._distance_matrix,
            world=self._world,
        )

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["id", "fleet", "charging_infrastructure"]
        )
        self._charging_operations.register_operator_reference(
            VirtualOperator(
                id=self._operator_reference.uid,
                fleet=self._operator_reference.fleet,
                charging_infrastructure=self._virtual_charging_infrastructure,
            )
        )

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
            bid_decay=self._operations_config.BID_DECAY,
            random_overbidding=self._operations_config.RANDOM_OVERBIDDING,
            overbid_prob=self._operations_config.OVERBID_PROB,
            bid_default=self._operations_config.BID_DEFAULT,
            operator_reference=self._operator_reference,
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
    def task_transactions(self):  # noqa: ANN201
        return self._charging_operations.task_transactions
