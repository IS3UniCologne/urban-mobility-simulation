import numpy as np
import pandas as pd

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet

from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter

def generate_fleet_config(distribution, n_cars = 1000, n_scooter = 500, n_kick_scooter = 500, n_bikes = 0, resolution = "hex_7"):
    """
    Calculate vehicle distribution based on activity distribution per mode.

    Input Distribution generated using Script: Prepare_Vehicle_Supply_Data
    :param distribution: DataFrame consisting of five columns ["hex_id", "cars_prob", "scooters_prob", "kick_scooters_prob", "bikes_prob"]
    :return: Fleet Configuration (i.e., where are how many vehciles distributed)
    """

    # Sample Supply Distribution for Cars
    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(np.random.multinomial(n_cars, cars_prob_arr, size=1).transpose(), columns=["car_count"])
    car_cnt.index = distribution.index
    distribution["cars"] = car_cnt["car_count"]

    # Sample Supply Distribution for Cars
    scooters_prob_arr = distribution["scooters_prob"].to_numpy()
    scooters_cnt = pd.DataFrame(np.random.multinomial(n_scooter, scooters_prob_arr, size=1).transpose(),
                                columns=["scooters_count"])
    scooters_cnt.index = distribution.index
    distribution["scooters"] = scooters_cnt["scooters_count"]

    # Sample Supply Distribution for Cars
    kick_scooters_prob_arr = distribution["kick_scooters_prob"].to_numpy()
    kick_scooters_cnt = pd.DataFrame(np.random.multinomial(n_kick_scooter, kick_scooters_prob_arr, size=1).transpose(), columns = ["kick_scooters_count"])
    kick_scooters_cnt.index = distribution.index
    distribution["kick_scooters"] = kick_scooters_cnt["kick_scooters_count"]

    # Sample Supply Distribution for Cars
    bikes_prob_arr = distribution["bikes_prob"].to_numpy()
    bikes_cnt = pd.DataFrame(np.random.multinomial(n_bikes, bikes_prob_arr, size=1).transpose(), columns = ["bikes_count"])
    bikes_cnt.index = distribution.index
    distribution["bikes"] = bikes_cnt["bikes_count"]

    if resolution == "hex_7":
        hex_column = "hex_id_7"

    # Slice fleet config
    fleet_config = distribution[[hex_column, "cars", "scooters", "kick_scooters", "bikes"]]

    return fleet_config


def generate_mixed_fleet(env, fleet_config, resolution = "hex_7"):
    """
    Generate a mixed shared vehicle fleet based on given fleet config.
    :param env: SimPy Environment (passed to vehicles)
    :param fleet_config: DataFrame with following 5 columns hex_id, cars, scooters, kick_scooters, bikes
    :param resolution: Geodesic Resolution (default = hex_7)
    :return: MixedSharedVehicleFleet Object
    """
    # New Fleet Object
    fleet = MixedSharedVehicleFleet()

    # Access to underlying geodesic environment
    geo_env = GeodesicEnvironment.getInstance()

    if resolution == "hex_7":
        hex_column = "hex_id_7"
    else:
        raise NotImplementedError()

    for index, row in fleet_config.iterrows():
        # We need to spawn vehicles in this hexagon
        hex_id = row[hex_column]

        # We need to spawn vehicles according to
        car_count = row["cars"]
        scooter_count = row["scooters"]
        kick_scooter_count = row["kick_scooters"]
        bike_count = row["bikes"]

        # Add Cars
        for current_car in range(car_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng)
            car = SharedCar(env, pos)
            fleet.add_shared_vehicle(car)

        # Add Scooter
        for current_scooter in range(scooter_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng)
            scooter = SharedScooter(env, pos)
            fleet.add_shared_vehicle(scooter)

        # Add Kick Scooter
        for current_kick_scooter in range(kick_scooter_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng)
            kick_scooter = SharedKickScooter(env, pos)
            fleet.add_shared_vehicle(kick_scooter)

        # Add Bikes
        #for current_bike in range(bike_count):
        #    rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
        #    pos = GeodesicPosition(rdm_lat, rdm_lng)
        #    bike = SharedBike(env, pos)
        #    fleet.add_shared_vehicle(kick_scooter)

    return fleet