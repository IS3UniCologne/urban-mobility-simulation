from __future__ import annotations  # noqa: D100

import random
from collections import Counter
from typing import TYPE_CHECKING

import pandas as pd
from beartype.door import die_if_unbearable  # like "assert isinstance(...)"
from beartype.roar import BeartypeDoorHintViolation
from simpy import AllOf

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.world.markets.auction import Auction

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import (
        SharedChargingAuctionConfig,
    )
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.world.markets.interfaces.bidder_interface import BidderInterface


class SharedChargingAuction(Auction):  # noqa: D101
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
        # bids are a list of n>=0 tuples of (integer, float, int)[capacity, bid price, bidder id] PER charging station, charging stations are denoted by h3hex ID (str)

        self._shared_charging_config = shared_charging_config
        self._bid_syntax = dict[str, list[tuple[int, int | float, int]]]

        # results are n=1 tuples of (integer, float)[capacity, clearing price] PER charging station, PER participant (int), charging stations are denoted by h3hex ID (str)
        self._result_syntax = dict[int, dict[str, tuple[int, float]]]

        self._participants = []
        self._bids = {}
        self._last_auction_state = {}
        self._location_results = {}
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

    def run(self):  # noqa: ANN201, D102
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

    def register_participant(self, participant: BidderInterface) -> int:  # noqa: D102
        self._participants.append(participant)
        return len(self._participants) - 1

    def clear(self) -> None:  # noqa: D102
        self._location_results = {}
        for location, capacity in self._charging_infrastructure.get_available_capacity(
            self._next_timeslot
        ).items():
            self._clear_single(location, capacity)

        # transform to dict of bidder id: dict of location id: (capacity, clearing price)
        self._result = pd.DataFrame(self._location_results).transpose().to_dict()

    def _clear_single(self, location: str, capacity: int) -> None:
        # uniform price clearing of capacity with fair tie breaking

        try:
            assert len(self._bids[location]) > 0
            location_bids = self._bids[location]
        except (AssertionError, KeyError):
            result = {}
            for participant in self._participants:
                result[participant.auction_participant_id] = (0, 0.0)
            self._location_results[location] = result
            return

        bids_df = pd.DataFrame.from_records(
            location_bids, columns=["capacity", "bid_price", "bidder_id"]
        )
        bids_df = bids_df.astype(
            {"capacity": int, "bid_price": float, "bidder_id": int}
        )
        bids_df.sort_values(by="bid_price", ascending=False, inplace=True)

        bids_df["cumulative_capacity"] = bids_df["capacity"].cumsum()

        if (bids_df["cumulative_capacity"] > capacity).any():
            clearing_price = bids_df.loc[
                bids_df["cumulative_capacity"] > capacity, "bid_price"
            ].values[0]
        else:
            clearing_price = 0

        if len(bids_df.loc[bids_df["bid_price"] == clearing_price, "bidder_id"]) > 1:
            capacity_to_tiebreak = (
                capacity
                - bids_df.loc[bids_df["bid_price"] > clearing_price, "capacity"].sum()
            )

            bidders_to_tiebreak = bids_df.loc[
                bids_df["bid_price"] == clearing_price, "bidder_id"
            ].values

            counts = Counter(
                self.__tiebreak_capacity(
                    capacity_to_tiebreak, bidders_to_tiebreak.tolist()
                )
            )
            tiebreak_allocation = [(id_, count) for id_, count in counts.items()]

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

        # result.sort_values(by="bidder_id", inplace=True)
        result = result.astype(
            {"bidder_id": int, "capacity": int, "clearing_price": float}
        )

        result_list = list(
            result[["bidder_id", "capacity", "clearing_price"]].itertuples(
                index=False, name=None
            )
        )

        submitted_ids = [result[0] for result in result_list]
        for participant in self._participants:
            if participant.auction_participant_id not in submitted_ids:
                result_list.append((participant.auction_participant_id, 0, 0.0))

        self._location_results[location] = {t[0]: (t[1], t[2]) for t in result_list}

    def _announce_results(self) -> None:
        for p in self._participants:
            p.result_announced.succeed(self._result[p.auction_participant_id])

        self.logger.debug(
            "Total Capacity Auctioned: %s",
            sum(
                [
                    result[0]
                    for location_id, location in self._location_results.items()
                    for participant, result in location.items()
                ]
            ),
        )

        self.cleared.succeed()
        self.cleared = self._env.event()

    def _update_auctionable_capacity(self) -> None:
        # update auctionable capacity for (next_timeslot, ..., next_timeslot + timeslot_duration)
        auctioned_capacity = {
            k: sum(c[0] for p, c in v.items())
            for k, v in self._location_results.items()
        }

        for timeslot in range(
            self._next_timeslot,
            self._next_timeslot + self._shared_charging_config.TIMESLOT_DURATION,
            self._shared_charging_config.AUCTION_INTERVAL,
        ):
            remaining_capacity = {
                k: v - auctioned_capacity[k]
                for k, v in self._charging_infrastructure.get_available_capacity(
                    timeslot
                ).items()
            }
            self._charging_infrastructure.update(
                availability=remaining_capacity, timeslot=timeslot
            )

    @property
    def result(self):  # noqa: ANN201, D102
        # it is illegal for other participants to know the full results in this type of auction
        raise NotImplementedError(
            "Not implemented for FleetChargingAuction, results are distributed through events"
        )

    @property
    def next_timeslot(self):  # noqa: ANN201, D102
        return self._next_timeslot

    def get_auctioned_capacity(self) -> dict[str, int]:  # noqa: D102
        return self._charging_infrastructure.get_available_capacity(self._next_timeslot)

    def _update_bids(self, single_bid):  # noqa: ANN001, ANN202
        for location, bid in single_bid.items():
            if location not in self._bids:
                self._bids[location] = []
            self._bids[location].extend(bid)

    @staticmethod
    def __tiebreak_capacity(capacity, among):  # noqa: ANN001, ANN205
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
