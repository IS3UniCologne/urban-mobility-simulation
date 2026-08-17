"""Distance-based bidding strategy for shared charging auctions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from simulation.operator.ride_hailing_fleet import RideHailingFleet

if TYPE_CHECKING:
    from simulation.helper.types import RegionId, SimTime
    from simulation.operator.interface.operator_interface import OperatorInterface


def get_bid(
    operator_reference: OperatorInterface,
    auctioned_timeslot: SimTime,
    auctioned_capacity: dict[RegionId, int],
    bid_default: float,
    bid_decay: float,
    random_overbidding: bool,
    overbid_prob: float,
    participant_id: int,
    state_of_charge_threshold: float,
    distance_matrix: pd.DataFrame,
    # return_bid_log=False,
) -> dict[RegionId, list[tuple[int, float, int]]] | None:
    """
    Compute charging capacity bids with distance-based prices.

    Prices decay exponentially with distance from the vehicle to the charging station.
    Cutoff distance is 10 km, beyond which bids are zero.

    Parameters
    ----------
    operator_reference : OperatorInterface
        Operator whose fleet needs charging, must own a RideHailingFleet.
    auctioned_timeslot : SimTime
        Start of the auctioned timeslot, unused.
    auctioned_capacity : dict of RegionId to int
        Available capacity per charging station hex.
    bid_default : float
        Bid price at distance zero.
    bid_decay : float
        Exponential decay rate per meter.
    random_overbidding : bool
        Whether to bid for more capacity than needed.
    overbid_prob : float
        Fraction of assigned vehicles re-entered when overbidding.
    participant_id : int
        Auction participant identifier included in each bid.
    state_of_charge_threshold : float
        State of charge below which vehicles need charging.
    distance_matrix : DataFrame
        Hex-to-hex distances in meters.

    Returns
    -------
    dict of RegionId to list of tuple or None
        (capacity, bid, participant_id) tuples per station hex, or None
        if no vehicle needs charging.

    Raises
    ------
    TypeError
        If the operator fleet is not a RideHailingFleet.
    """
    fleet = operator_reference.fleet
    if not isinstance(fleet, RideHailingFleet):
        raise TypeError("Fleet must be of type RideHailingFleet")
    vehicles_to_charge = fleet.mark_vehicles_to_be_charged(state_of_charge_threshold)

    if len(vehicles_to_charge) == 0:
        return None

    distance_records = []

    relevant_distance_matrix = distance_matrix.loc[list(auctioned_capacity.keys())]
    for vehicle in vehicles_to_charge:
        vehicle_hex = vehicle.position.get_region_id()
        vehicle_id = vehicle.uid

        # Get nearest charging station (.loc -> destination, [[]] -> Origin)
        sorted_charging_station_list = (
            relevant_distance_matrix[vehicle_hex].sort_values(ascending=True).to_dict()
        )

        for cs in auctioned_capacity:
            distance_records.append(
                {
                    "vehicle_id": vehicle_id,
                    "cs": cs,
                    "distance": sorted_charging_station_list[cs],
                }
            )

    distances = pd.DataFrame.from_records(distance_records)
    cumulative_distances = (
        distances.loc[:, ["cs", "distance"]].groupby("cs").sum().reset_index()
    )
    sorted_stations = cumulative_distances.sort_values(by="distance", ascending=True)
    sorted_stations["capacity"] = [
        auctioned_capacity[cs] for cs in sorted_stations.loc[:, "cs"].values
    ]

    # LINEAR DECAY -> will lead to zero
    # distances["bid"] = (bid_default - bid_decay * distances["distance"]).apply(
    #     lambda x: max(0, x)
    # )

    # EXPONENTIAL DECAY -> will not lead to zero bids
    # TODO: parametrize bidding cutoff - here we use 10km
    distances["bid"] = np.where(
        distances["distance"] <= 10000,
        np.exp(-bid_decay * distances["distance"]) * bid_default,
        0,
    )

    bid_log = []  # list of tuple (CS, id, bid) -> can also use this to see which cars already submitted bids
    blacklist = []  # vehicle ids for which bids already have been submitted are not considered for additional charging
    sorted_stations_capacity = sorted_stations.set_index("cs")["capacity"].to_dict()

    for cs in sorted_stations["cs"].values:
        dist_frame = distances[
            (distances["cs"] == cs) & (~distances["vehicle_id"].isin(blacklist))
        ]
        dist_frame = dist_frame[dist_frame["bid"] != 0]
        capacity = sorted_stations_capacity[cs]
        dist_frame = dist_frame.head(capacity)
        to_log = dist_frame.loc[:, ["cs", "vehicle_id", "bid"]]

        for row in to_log.itertuples(index=False, name=None):
            bid_log.append(tuple(row))

        vehicle_ids = to_log["vehicle_id"].tolist()
        blacklist.extend(
            np.random.choice(
                vehicle_ids, int(len(vehicle_ids) / (1 / overbid_prob)), replace=False
            )
            if random_overbidding
            else vehicle_ids
        )

    df = pd.DataFrame.from_records(bid_log, columns=["cs", "vehicle_id", "bid"])
    grouped = df.groupby(["cs", "bid"]).size().reset_index(name="count")
    bids: dict[RegionId, list[tuple[int, float, int]]] = {}
    for row in grouped.itertuples(index=False, name=None):
        cs, bid, capacity = row
        if cs not in bids:
            bids[cs] = [(capacity, bid, participant_id)]
        else:
            bids[cs].append((capacity, bid, participant_id))

    return bids


# verify format for bid submisssion
# 1 timeslot -> dict; key: station hex; value: list of tuples (capacity, bid, self_id)
# get bids into correct form
# test
