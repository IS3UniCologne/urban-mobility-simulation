import logging
from collections import namedtuple

from simpy import Environment

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.algorithms.distance_based_bidding_strategy import (
    get_bid,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.world.markets.auction import Auction
from simulation.world.markets.interfaces.bidder_interface import BidderInterface


class RideHailingSharedChargingOperations(OperationsInterface, BidderInterface):

    __slots__ = ( "_env", "_auction", "_bidding_parameters", "_state_of_charge_threshold", "_distance_matrix", "_config", "_charging_operations", "_virtual_charging_infrastructure")

    def __init__(
        self,
        env: Environment,
        auction: Auction,
        # bidding_strategy,
        bidding_parameters: dict,
        state_of_charge_threshold: float,
        distance_matrix=None,
    ):
        OperationsInterface.__init__(self, env)
        BidderInterface.__init__(self, env, auction)

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        # self._bidding_strategy = bidding_strategy
        self._bidding_parameters = bidding_parameters
        self._state_of_charge_threshold = state_of_charge_threshold
        self._distance_matrix = distance_matrix

        self._config = Configuration()

        self._charging_operations = None

    def execute(self):
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            env=self._env,
            charging_infrastructure=self._operator_reference.charging_infrastructure,
            lookahead=self._config.auction.AUCTION_START
            + self._config.shared_charging_auction.AUCTION_LOOKAHEAD,
        )

        self._charging_operations = RideHailingBaseChargingOperations(
            env=self._env,
            distance_matrix=self._distance_matrix,
            time_between_operations=self._config.shared_charging_auction.AUCTION_INTERVAL,
            operation_duration=None,  # does not matter
            available_modes=self._config.ride_hailing_global.AVAILABLE_VEHICLE_MODES,
            available_modes_supply=self._config.ride_hailing_global.AVAILABLE_MODES_SUPPLY,
            state_of_charge_threshold=self._state_of_charge_threshold,
            allow_queue=False,  # no queue, only reserved slots
        )

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["id", "fleet", "charging_infrastructure"]
        )
        self._charging_operations.register_operator_reference(
            VirtualOperator(
                id=self._operator_reference.id,
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

    def _bid_for_capacity(self):
        yield self._auction.open_for_bidding
        # timeslots are denoted by their start time and have length `self._config.shared_charging_auction.TIMESLOT_DURATION`
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

        # TODO: refactor to be a method of somethign like "BiddingStrategy"
        # TODO: right now we track bids through the auction, maybe we can use transactions for that?
        self._bids = get_bid(
            auctioned_timeslot=auctioned_timeslot,
            auctioned_capacity=auctioned_capacity,
            bidding_parameters=self._bidding_parameters,
            operator_referece=self._operator_reference,
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
        logging.debug(
            "Bids placed for timeslot %s",
            auctioned_timeslot,
            extra={
                "clazz": self.__class__.__name__,
                "oid": self._auction_participant_id,
            },
        )

        self._result = yield self.result_announced
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
            availability={k: v[0] for k, v in self._result.items()},
            timeslot=auctioned_timeslot,
        )

    def _delay_charging_operations(self):
        # Logic: Wait until t=1 because we start auctions at t=0+(auction_interval) and then the charging operations process can run in intervals of auction_interval, this works because the auction is instant from simulation-time perspective

        yield self._env.timeout(1)
        self._env.process(self._charging_operations.execute())

    @property
    def task_transactions(self):
        return self._charging_operations.task_transactions
