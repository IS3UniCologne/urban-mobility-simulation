import logging

from simpy import Environment

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
        charging_operations: RideHailingChargingOperations = None,
    ):
        OperationsInterface.__init__(self, env)
        BidderInterface.__init__(self, env, auction)

        self._auction_participant_id = self._auction.register_participant(self)
        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        # self._bidding_strategy = bidding_strategy
        self._bidding_parameters = bidding_parameters
        self._charging_operations = charging_operations
        self._state_of_charge_threshold = state_of_charge_threshold
        self._distance_matrix = distance_matrix

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
        logging.debug(
            "Auction opened for timeslot %s",
            auctioned_timeslot,
            extra={
                "clazz": self.__class__.__name__,
                "oid": self._auction_participant_id,
            },
        )

        # TODO: implement real bid logic
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

        try:
            {k: v[0] for k, v in result.items()}
        except Exception:
            pass

        self._virtual_charging_infrastructure.update(
            auctioned_timeslot, {k: v[0] for k, v in result.items()}
        )

    def _charge_vehicles(self):
        # TODO: this can use most of the ridehailing_charging_operations.py logic, but must work on to the virtual charging infrastructure view instead of raw infrastructure
        yield self._env.timeout(1)
