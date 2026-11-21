"""Uniform-price auction of charging station capacity, shared by several operators."""

from __future__ import annotations

import random
from collections import Counter
from typing import TYPE_CHECKING, NoReturn, TypeAlias

import pandas as pd
from beartype.door import die_if_unbearable  # like "assert isinstance(...)"
from beartype.roar import BeartypeDoorHintViolation
from simpy import AllOf

from simulation.helper.types import RegionId
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.world.markets.auction import Auction

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import (
        SharedChargingAuctionConfig,
    )
    from simulation.infrastructure.charging_stations.charging_infrastructure import (
        ChargingInfrastructure,
    )
    from simulation.world.markets.interfaces.bidder_interface import BidderInterface

# Bids per location: (capacity, bid price, bidder id) tuples
_Bids: TypeAlias = dict[RegionId, list[tuple[int, float, int]]]
# Allocation per location: (capacity, clearing price)
_Allocations: TypeAlias = dict[RegionId, tuple[int, float]]
_AllocationsByBidder: TypeAlias = dict[int, _Allocations]


class SharedChargingAuction(Auction[_Bids, _AllocationsByBidder]):
    """
    Auction that sells the capacity of shared charging stations in fixed timeslots.

    Each round opens AUCTION_LOOKAHEAD before the next timeslot.
    Every registered bidder places its bids and then succeeds its bidding_done event.
    The auction clears each location at a uniform price and breaks ties at random.
    Each bidder then receives only its own allocations through its result_announced event.
    The capacity sold is taken off the auctionable capacity of the timeslots it covers.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    charging_infrastructure : ChargingInfrastructure
        Physical charging infrastructure whose capacity is sold.
    shared_charging_config : SharedChargingAuctionConfig
        Configuration for the shared charging auction.
    """

    __slots__ = (
        "_charging_infrastructure",
        "_charging_locations",
        "_last_auction_state",
        "_location_results",
        "_next_timeslot",
        "_participants",
        "_shared_charging_config",
    )

    def __init__(
        self,
        sim: SimulationContext,
        charging_infrastructure: ChargingInfrastructure,
        shared_charging_config: SharedChargingAuctionConfig,
    ) -> None:
        super().__init__(sim)

        self._env = sim.env

        self._shared_charging_config = shared_charging_config
        # beartype does not accept an int for a float, so the price is int | float here
        self._bid_syntax = dict[str, list[tuple[int, int | float, int]]]
        self._result_syntax = _AllocationsByBidder
        # results are n=1 tuples of (integer, float)[capacity, clearing price] PER charging station, PER participant (int), charging stations are denoted by h3hex ID (str)
        self._participants: list[BidderInterface[_Bids, _AllocationsByBidder]] = []
        self._bids = {}
        self._last_auction_state: dict[str, object] = {}
        self._location_results: dict[RegionId, dict[int, tuple[int, float]]] = {}
        self._next_timeslot = (
            self._shared_charging_config.AUCTION_START
            + self._shared_charging_config.AUCTION_LOOKAHEAD
        )

        # init auction view on charging infrastructure
        # this is a view that tells the auctioneer how much capacity is up for auction
        self._charging_infrastructure = VirtualChargingInfrastructure(
            sim=sim,
            charging_infrastructure=charging_infrastructure,
            lookahead=self._shared_charging_config.AUCTION_START
            + self._shared_charging_config.AUCTION_LOOKAHEAD,
            use_virtual_cs=False,
        )
        for timeslot in range(
            self._shared_charging_config.AUCTION_START
            + self._shared_charging_config.AUCTION_LOOKAHEAD,
            self._shared_charging_config.AUCTION_END
            + self._shared_charging_config.AUCTION_INTERVAL,
            self._shared_charging_config.AUCTION_INTERVAL,
        ):
            self._charging_infrastructure.update(
                availability={
                    station.location: station.capacity
                    for station in charging_infrastructure.charging_stations
                },
                timeslot=timeslot,
            )

    def run(self) -> Generator[Event, None, None]:
        """
        Run one auction round per timeslot until the last timeslot.

        Yields
        ------
        Event
            Wait until the round opens, then until every bidder has placed its bids.
        """
        while True:
            if (
                self._next_timeslot
                > self._shared_charging_config.AUCTION_END
                - self._shared_charging_config.TIMESLOT_DURATION
            ):
                self.logger.info("Auction stops, last timeslot reached.")
                break

            open_at = (
                self._next_timeslot - self._shared_charging_config.AUCTION_LOOKAHEAD
            )

            if self._env.now <= open_at:
                yield self._env.timeout(open_at - self._env.now)

            self._is_open = True
            self.open_for_bidding.succeed()
            self.logger.info(
                "Auction open. Auctionable capacity for next timeslot (%s): %s",
                self._next_timeslot,
                sum(
                    self._charging_infrastructure.get_available_capacity(
                        self._next_timeslot
                    ).values()
                ),
            )

            yield AllOf(self._env, [x.bidding_done for x in self._participants])
            self.logger.debug("Bids received. Starting clearing")

            auctioned_timeslot = self._next_timeslot
            auctioned_capacity = self._charging_infrastructure.get_available_capacity(
                self._next_timeslot
            ).copy()

            self.clear()
            try:
                die_if_unbearable(self._result, self._result_syntax)
            except BeartypeDoorHintViolation:
                self.logger.error(
                    "Result of SharedChargingAuction must be a dict of (participant id, dict of (location id, (capacity, clearing price)))"
                )
            self._announce_results()

            self._last_auction_state = {
                "timeslot": auctioned_timeslot,
                "available_capacity": auctioned_capacity,
                "bids": self._bids.copy(),
                "results": self._location_results.copy(),
            }

            self._bids = {}
            self._update_auctionable_capacity()

            self._next_timeslot = (
                self._next_timeslot + self._shared_charging_config.AUCTION_INTERVAL
            )
            self.logger.debug(
                "Results announced. Closing auction until %s", self._next_timeslot
            )

            self._is_open = False
            self.open_for_bidding = self._env.event()

    def register_participant(
        self, participant: BidderInterface[_Bids, _AllocationsByBidder]
    ) -> int:
        """
        Register a bidder with the auction.

        Parameters
        ----------
        participant : BidderInterface
            Bidder to register.

        Returns
        -------
        int
            Assigned participant identifier, the index of the bidder in registration order.
        """
        self._participants.append(participant)
        return len(self._participants) - 1

    def clear(self) -> None:
        """Clear every location of the next timeslot and collect the allocations per bidder."""
        self._location_results = {}
        for location, capacity in self._charging_infrastructure.get_available_capacity(
            self._next_timeslot
        ).items():
            self._clear_single(location, capacity)

        result: _AllocationsByBidder = {}
        for location, allocations in self._location_results.items():
            for bidder_id, allocation in allocations.items():
                result.setdefault(bidder_id, {})[location] = allocation
        self._result = result

    def _clear_single(self, location: RegionId, capacity: int) -> None:
        # uniform price clearing of capacity with fair tie breaking

        location_bids = self._bids.get(location)
        if not location_bids:
            self._location_results[location] = {
                participant.auction_participant_id: (0, 0.0)
                for participant in self._participants
            }
            return

        bids_df = pd.DataFrame.from_records(
            location_bids, columns=["capacity", "bid_price", "bidder_id"]
        )
        bids_df = bids_df.astype(
            {"capacity": int, "bid_price": float, "bidder_id": int}
        )
        bids_df = bids_df.sort_values(by="bid_price", ascending=False)

        bids_df["cumulative_capacity"] = bids_df["capacity"].cumsum()

        if (bids_df["cumulative_capacity"] > capacity).any():
            clearing_price = float(
                bids_df.loc[
                    bids_df["cumulative_capacity"] > capacity, "bid_price"
                ].to_numpy()[0]
            )
        else:
            clearing_price = 0.0

        if len(bids_df.loc[bids_df["bid_price"] == clearing_price, "bidder_id"]) > 1:
            capacity_to_tiebreak = int(
                capacity
                - bids_df.loc[bids_df["bid_price"] > clearing_price, "capacity"].sum()
            )

            bidders_to_tiebreak = bids_df.loc[
                bids_df["bid_price"] == clearing_price, "bidder_id"
            ].to_numpy()

            counts = Counter(
                self.__tiebreak_capacity(
                    capacity_to_tiebreak, bidders_to_tiebreak.tolist()
                )
            )
            tiebreak_allocation = list(counts.items())

            result = pd.concat(
                [
                    bids_df.loc[
                        bids_df["bid_price"] > clearing_price, ["bidder_id", "capacity"]
                    ],
                    pd.DataFrame(
                        tiebreak_allocation, columns=["bidder_id", "capacity"]
                    ),
                ],
                ignore_index=True,
            )
        else:
            result = pd.concat(
                [
                    bids_df.loc[
                        bids_df["cumulative_capacity"] <= capacity,
                        ["bidder_id", "capacity", "cumulative_capacity"],
                    ],
                    bids_df.loc[
                        bids_df["cumulative_capacity"] > capacity,
                        ["bidder_id", "capacity", "cumulative_capacity"],
                    ].head(1),
                ],
                ignore_index=True,
            )

            result.loc[result.index[-1], "capacity"] = result.loc[
                result.index[-1], "capacity"
            ] - max((result.loc[result.index[-1], "cumulative_capacity"] - capacity), 0)

        result = result.groupby("bidder_id").agg({"capacity": "sum"}).reset_index()
        result["clearing_price"] = clearing_price

        # result = result.sort_values(by="bidder_id")
        result = result.astype(
            {"bidder_id": int, "capacity": int, "clearing_price": float}
        )

        result_list: list[tuple[int, int, float]] = list(
            result[["bidder_id", "capacity", "clearing_price"]].itertuples(
                index=False, name=None
            )
        )

        submitted_ids = [bidder_id for bidder_id, _, _ in result_list]
        for participant in self._participants:
            if participant.auction_participant_id not in submitted_ids:
                result_list.append((participant.auction_participant_id, 0, 0.0))

        self._location_results[location] = {
            bidder_id: (allocated, price) for bidder_id, allocated, price in result_list
        }

    def _announce_results(self) -> None:
        assert self._result is not None
        for p in self._participants:
            p.result_announced.succeed(self._result[p.auction_participant_id])

        self.logger.debug(
            "Total Capacity Auctioned: %s",
            sum(
                allocation[0]
                for allocations in self._location_results.values()
                for allocation in allocations.values()
            ),
        )

        self.cleared.succeed()
        self.cleared = self._env.event()

    def _update_auctionable_capacity(self) -> None:
        # update auctionable capacity for (next_timeslot, ..., next_timeslot + timeslot_duration)
        auctioned_capacity = {
            location: sum(allocation[0] for allocation in allocations.values())
            for location, allocations in self._location_results.items()
        }

        for timeslot in range(
            self._next_timeslot,
            self._next_timeslot + self._shared_charging_config.TIMESLOT_DURATION,
            self._shared_charging_config.AUCTION_INTERVAL,
        ):
            remaining_capacity = {
                location: capacity - auctioned_capacity[location]
                for location, capacity in self._charging_infrastructure.get_available_capacity(
                    timeslot
                ).items()
            }
            self._charging_infrastructure.update(
                availability=remaining_capacity, timeslot=timeslot
            )

    @property
    def result(self) -> NoReturn:
        """Refuse to give the full result, since each bidder may see only its own allocations."""
        raise NotImplementedError(
            "Not implemented for SharedChargingAuction, results are distributed through events"
        )

    @property
    def next_timeslot(self) -> int:
        """Start of the timeslot the next or open round sells."""
        return self._next_timeslot

    @property
    def lookahead(self) -> int:
        """Time between the opening of a round and the start of the timeslot it sells."""
        return self._shared_charging_config.AUCTION_LOOKAHEAD

    def get_auctioned_capacity(self) -> dict[RegionId, int]:
        """Return the capacity per location on sale for the next timeslot."""
        return self._charging_infrastructure.get_available_capacity(self._next_timeslot)

    def _update_bids(self, single_bid: _Bids) -> None:
        """
        Merge a single bid into the bids of the open round.

        Parameters
        ----------
        single_bid : dict of RegionId to list of (int, float, int)
            Capacity, bid price and bidder id per location.
        """
        for location, bid in single_bid.items():
            self._bids.setdefault(location, []).extend(bid)

    @staticmethod
    def __tiebreak_capacity(capacity: int, among: list[int]) -> list[int]:
        if len(among) >= capacity:
            return random.sample(among, capacity)
        else:
            n = int((len(among) - 1) / capacity) + 1
            num_ids_to_allocate_n = n * capacity
            allocated_ids = (
                among * (num_ids_to_allocate_n // len(among))
                + among[: num_ids_to_allocate_n % len(among)]
            )
            random.shuffle(allocated_ids)
            remaining_ids = allocated_ids[capacity:]
            allocated_ids = allocated_ids[:capacity]
            allocated_ids.extend(
                random.sample(remaining_ids, capacity - len(allocated_ids))
            )
            return allocated_ids
