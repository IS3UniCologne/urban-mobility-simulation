import numpy as np
import pandas as pd


def get_bid(
    operator_referece,
    auctioned_timeslot,
    auctioned_capacity,
    bidding_parameters,
    participant_id,
    state_of_charge_threshold,
    distance_matrix,
    # return_bid_log=False,
):
    auctioned_capacity = auctioned_capacity
    auctioned_timeslot = auctioned_timeslot
    operator_referece = operator_referece
    participant_id = participant_id
    vehicles_to_charge = operator_referece.fleet.mark_vehicles_to_be_charged(
        state_of_charge_threshold
    )

    if len(vehicles_to_charge) == 0:
        return None

    bid_default = bidding_parameters["bid_default"]
    bid_decay = bidding_parameters["bid_decay"]

    distances = []

    relevant_distance_matrix = distance_matrix.loc[auctioned_capacity.keys()]
    for vehicle in vehicles_to_charge:
        hex = vehicle.position.get_hexagon(return_geom=False)[0]
        id = vehicle.id

        # Get nearest charging station (.loc -> destination, [[]] -> Origin)
        sorted_charging_station_list = (
            relevant_distance_matrix[hex].sort_values(ascending=True).to_dict()
        )

        for cs in auctioned_capacity:
            distances.append(
                {
                    "vehicle_id": id,
                    "CS": cs,
                    "distance": sorted_charging_station_list[cs],
                }
            )

    distances = pd.DataFrame.from_records(distances)
    cumulative_distances = (
        distances.loc[:, ["CS", "distance"]].groupby("CS").sum().reset_index()
    )
    sorted_stations = cumulative_distances.sort_values(by="distance", ascending=True)
    sorted_stations["capacity"] = [
        auctioned_capacity[cs] for cs in sorted_stations.loc[:, "CS"].values
    ]

    # LINEAR DECAY -> will lead to zero
    # distances["bid"] = (bid_default - bid_decay * distances["distance"]).apply(
    #     lambda x: max(0, x)
    # )

    # EXPONENTIAL DECAY -> will not lead to zero bids
    distances["bid"] = np.exp(-bid_decay * distances["distance"]) * bid_default

    bid_log = []  # list of tuple (CS, id, bid) -> can also use this to see which cars already submitted bids
    blacklist = []  # vehicle ids for which bids already have been submitted are not considered for additional charging
    for cs in sorted_stations["CS"].values:
        blacklist = [i[1] for i in bid_log]  # reads id from bid log
        distances = distances[~distances["vehicle_id"].isin(blacklist)]
        capacity = sorted_stations.loc[sorted_stations["CS"] == cs, "capacity"].values[
            0
        ]
        distances = distances.head(capacity)
        distances["cs"] = cs
        to_log = distances.loc[:, ["cs", "vehicle_id", "bid"]]

        for row in to_log.itertuples(index=False, name=None):
            bid_log.append(tuple(row))

    df = pd.DataFrame.from_records(bid_log, columns=["cs", "vehicle_id", "bid"])
    grouped = df.groupby(["cs", "bid"]).size().reset_index(name="count")
    bids = {}
    for row in grouped.itertuples(index=False):
        cs = row.cs
        bid = row.bid
        capacity = row.count
        if cs not in bids:
            bids[cs] = [(capacity, bid, participant_id)]
        else:
            bids[cs].append((capacity, bid, participant_id))

    return bids


# verify format for bid submisssion
# 1 timeslot -> dict; key: station hex; value: list of tuples (capacity, bid, self_id)
# get bids into correct form
# test
