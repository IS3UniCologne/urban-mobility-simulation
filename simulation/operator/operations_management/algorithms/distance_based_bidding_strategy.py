import numpy as np
import pandas as pd


def get_bid(  # noqa: ANN201
    operator_reference,  # noqa: ANN001
    auctioned_timeslot,  # noqa: ANN001
    auctioned_capacity,  # noqa: ANN001
    bid_default: float,
    bid_decay: float,
    random_overbidding: bool,
    overbid_prob: float,
    participant_id,  # noqa: ANN001
    state_of_charge_threshold,  # noqa: ANN001
    distance_matrix,  # noqa: ANN001
    # return_bid_log=False,
):
    auctioned_capacity = auctioned_capacity
    auctioned_timeslot = auctioned_timeslot
    operator_reference = operator_reference
    participant_id = participant_id
    vehicles_to_charge = operator_reference.fleet.mark_vehicles_to_be_charged(
        state_of_charge_threshold
    )

    if len(vehicles_to_charge) == 0:
        return None

    distances = []

    relevant_distance_matrix = distance_matrix.loc[auctioned_capacity.keys()]
    for vehicle in vehicles_to_charge:
        hex = vehicle.position.get_region_id()
        id = vehicle.uid

        # Get nearest charging station (.loc -> destination, [[]] -> Origin)
        sorted_charging_station_list = (
            relevant_distance_matrix[hex].sort_values(ascending=True).to_dict()
        )

        for cs in auctioned_capacity:
            distances.append(
                {
                    "vehicle_id": id,
                    "cs": cs,
                    "distance": sorted_charging_station_list[cs],
                }
            )

    distances = pd.DataFrame.from_records(distances)
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
