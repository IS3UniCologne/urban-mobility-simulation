import logging
from collections import namedtuple

from simpy import Environment

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.distance_based_bidding_strategy import (
    get_bid,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.ridehailing_charging_operations import (
    RideHailingChargingOperations,
)
from simulation.world.markets.auction import Auction
from simulation.world.markets.interfaces.bidder_interface import BidderInterface


class RideHailingSharedChargingOperations(OperationsInterface, BidderInterface):
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

        self._auction_participant_id = self._auction.register_participant(self)
        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        # self._bidding_strategy = bidding_strategy
        self._bidding_parameters = bidding_parameters
        self._state_of_charge_threshold = state_of_charge_threshold
        self._distance_matrix = distance_matrix

        self._config = Configuration.instance()

        self._charging_operations = None

    @property
    def auction_participant_id(self):
        return self._auction_participant_id

    def execute(self):
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            self._env, self._operator_reference.charging_infrastructure
        )

        self._charging_operations = RideHailingChargingOperations(
            env=self._env,
            distance_matrix=self._distance_matrix,
            time_between_operations=self._config.ridehailing_operator_config.operations_start,
            operation_duration=self._config.ridehailing_operator_config.operations_duration,
            available_modes=self._config.ridehailing_operator_config.available_modes,
            available_modes_supply=self._config.ridehailing_operator_config.available_modes_supply,
            state_of_charge_threshold=self._state_of_charge_threshold,
        )

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["fleet", "charging_infrastructure"]
        )
        self._charging_operations.register_operator_reference(
            VirtualOperator(
                fleet=self._operator_reference.fleet,
                charging_infrastructure=self._virtual_charging_infrastructure,
            )
        )

        self._env.process(self._charging_operations.execute())

        while True:
            # this operator has two jobs to do:
            # 1) bid for capacity
            # 2) charge vehicles - done by self._charging_operations

            yield self._env.process(self._bid_for_capacity())

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

        # TODO: refactor to be a method of somethign like "BiddingStrategy"
        bid = get_bid(
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

        if bid is not None:
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
