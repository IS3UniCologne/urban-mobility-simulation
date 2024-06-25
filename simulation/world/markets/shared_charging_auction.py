import random
from collections import Counter
from typing import Dict, Tuple

import pandas as pd
from simpy import Environment

from simulation.infrastructure.charging_stations.charging_station import ChargingStation
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.world.markets.auction import Auction
from simulation.world.markets.interfaces.bidder_interface import BidderInterface
from tracking.tracking_interface import TrackingInterface


class SharedChargingAuction(Auction, TrackingInterface):
    __slots__ = (
        "_participants",
        "_charging_locations",
        "_next_timeslot",
        "_location_results",
    )

    exposes = ["_next_timeslot", "_bids", "_location_results"]

    def __init__(
        self,
        env: Environment,
        start_condition,
        end_condition,
        charging_infrastructure: VirtualChargingInfrastructure,
    ) -> None:
        super().__init__(env, start_condition, end_condition)

        # bids are n>=0 tuples of (integer, float, int)[capacity, bid price, bidder id] PER charging station, charging stations are denoted by h3hex ID (str)
        self._bid_syntax = Dict[str, Tuple[int, float, int]]

        # results are n=1 tuples of (integer, float)[capacity, clearing price] PER charging station, PER participant (int), charging stations are denoted by h3hex ID (str)
        self._result_syntax = Dict[int, Dict[str, Tuple[int, float]]]

        self._participants = []
        self._charging_locations = charging_infrastructure
        self._location_results = {}
        self._next_timeslot = self._config.auction_config.auction_start

    def run(self):
        while True:
            if self._env.now() < self._next_timeslot:
                yield self._env.timeout(self._next_timeslot - self._env.now)

            self._is_open = True
            self.open_for_bidding.succeed()

            # wait for bids?

            self.clear()
            assert isinstance(self._result, self._result_syntax)
            self._announce_results()

            self._next_timeslot = (
                self._next_timeslot + self._config.auction_config.auction_interval
            )
            self._is_open = False

    def register_participant(self, participant: BidderInterface) -> int:
        self._participants.append(participant)
        return len(self._participants)

    def clear(self) -> None:
        for c in self._charging_locations:
            self._clear_single(c)

        # transform to dict of bidder id: dict of location id: (capacity, clearing price)
        self._result = pd.DataFrame(self._location_results).transpose().to_dict()

    def _clear_single(self, charging_location: ChargingStation) -> None:
        # uniform price clearing of capacity with fair tie breaking
        location_id = charging_location.location
        location_bids = self._bids[charging_location]
        capacity = charging_location.capacity

        bids_df = pd.DataFrame.from_records(
            location_bids, columns=["capacity", "bid_price", "bidder_id"]
        )
        bids_df = bids_df.astype(
            {"capacity": int, "bid_price": float, "bidder_id": int}
        )
        bids_df.sort_values(by="bid_price", ascending=False, inplace=True)

        bids_df["cumulative_capacity"] = bids_df["capacity"].cumsum()

        clearing_price = bids_df.loc[
            bids_df["cumulative_capacity"] >= capacity, "bid_price"
        ].values[0]

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
            ] - (result.loc[result.index[-1], "cumulative_capacity"] - capacity)

        result = (
            bids_df[["bidder_id"]]
            .merge(
                result[["bidder_id", "capacity"]],
                left_on="bidder_id",
                right_on="bidder_id",
                how="left",
            )
            .fillna(0)
        )

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

        self._location_results[location_id] = {t[0]: (t[1], t[2]) for t in result_list}

    def _announce_results(self) -> None:
        for p in self._participants:
            p.result_announced.succeed(self._result[p])

        self._charging_locations.update(self._location_results)

    @property
    def result(self):
        # it is illegal for other participants to know the full results in this type of auction
        raise NotImplementedError(
            "Not implemented for FleetChargingAuction, results are distributed through events"
        )

    @property
    def next_timeslot(self):
        return self._next_timeslot

    @staticmethod
    def __tiebreak_capacity(capacity, among):
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

    def dump(self, exposed_only: bool = True) -> Dict:
        return {
            "_next_timeslot": self._next_timeslot,
            "_bids": self._bids,
            "_location_results": self._location_results,
        }
