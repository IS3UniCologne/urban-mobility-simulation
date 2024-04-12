import numpy as np
import pandas as pd

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.operator.mixed_ride_hailing_fleet import MixedRideHailingFleet
from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
from simulation.vehicle.autonomous_car import AutonomousCar
from simulation.vehicle.ride_hailing_car import RideHailingCar
from simulation.vehicle.shared_bike import SharedBike
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter


def generate_fleet_config(
    distribution,
    n_cars=1000,
    n_scooter=500,
    n_kick_scooter=500,
    n_bikes=500,
    seed=42,
    allocation_method="historical",
    allocation=np.random.randint(low=20, high=50, size=213),
):
    """
    Calculate vehicle distribution based on activity distribution per mode.

    Input Distribution generated using Script: Prepare_Vehicle_Supply_Data
    :param distribution: DataFrame consisting of five columns ["hex_id", "cars_prob", "scooters_prob", "kick_scooters_prob", "bikes_prob"]
    :return: Fleet Configuration (i.e., where are how many vehciles distributed)
    """

    # Random Number Generator
    random = np.random.RandomState(seed)

    # Sample Supply Distribution for Cars
    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        random.multinomial(n_cars, cars_prob_arr, size=1).transpose(),
        columns=["car_count"],
    )
    car_cnt.index = distribution.index
    distribution["cars"] = car_cnt["car_count"]

    # Sample Supply Distribution for Cars
    scooters_prob_arr = distribution["scooters_prob"].to_numpy()
    scooters_cnt = pd.DataFrame(
        random.multinomial(n_scooter, scooters_prob_arr, size=1).transpose(),
        columns=["scooters_count"],
    )
    scooters_cnt.index = distribution.index
    distribution["scooters"] = scooters_cnt["scooters_count"]

    # Sample Supply Distribution for Cars
    kick_scooters_prob_arr = distribution["kick_scooters_prob"].to_numpy()
    kick_scooters_cnt = pd.DataFrame(
        random.multinomial(n_kick_scooter, kick_scooters_prob_arr, size=1).transpose(),
        columns=["kick_scooters_count"],
    )
    kick_scooters_cnt.index = distribution.index
    distribution["kick_scooters"] = kick_scooters_cnt["kick_scooters_count"]

    # Sample Supply Distribution for Cars
    bikes_prob_arr = distribution["bikes_prob"].to_numpy()
    bikes_cnt = pd.DataFrame(
        random.multinomial(n_bikes, bikes_prob_arr, size=1).transpose(),
        columns=["bikes_count"],
    )
    bikes_cnt.index = distribution.index
    distribution["bikes"] = bikes_cnt["bikes_count"]

    hex_column = Configuration.instance().spatial_resolution_column

    # Slice fleet config
    fleet_config = distribution[
        [hex_column, "cars", "scooters", "kick_scooters", "bikes"]
    ]

    return fleet_config


def generate_ridehailing_fleet_config(
    distribution,
    n_cars=1000,
    n_AVs=500,
    seed=42,
    allocation_method="historical",
    allocation=np.random.randint(low=20, high=50, size=213),
):
    """
    Calculate vehicle distribution based on activity distribution per mode.

    Input Distribution generated using Script: Prepare_Vehicle_Supply_Data
    :param distribution: DataFrame consisting of five columns ["hex_id", "cars_prob", "scooters_prob", "kick_scooters_prob", "bikes_prob"]
    :return: Fleet Configuration (i.e., where are how many vehciles distributed)
    """

    # Random Number Generator
    random = np.random.RandomState(seed)

    config = Configuration.instance()
    EV_peneteration = config.get_EV_penetration()
    AV_peneteration = config.get_AV_penetration()
    n_AVs = int(AV_peneteration * n_cars)
    n_non_AVs = int((1 - AV_peneteration) * n_cars)
    n_EVs = int(EV_peneteration * n_non_AVs)
    n_cars = int((1 - EV_peneteration) * n_non_AVs)

    # Sample Supply Distribution for Cars
    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        random.multinomial(n_cars, cars_prob_arr, size=1).transpose(),
        columns=["car_count"],
    )
    car_cnt.index = distribution.index
    distribution["cars"] = car_cnt["car_count"]

    # Sample Supply Distribution for Cars
    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        random.multinomial(n_EVs, cars_prob_arr, size=1).transpose(),
        columns=["car_count"],
    )
    car_cnt.index = distribution.index
    distribution["EVs"] = car_cnt["car_count"]

    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        random.multinomial(n_AVs, cars_prob_arr, size=1).transpose(),
        columns=["car_count"],
    )
    car_cnt.index = distribution.index
    distribution["AVs"] = car_cnt["car_count"]

    # Sample Supply Distribution for Cars
    hex_column = Configuration.instance().spatial_resolution_column

    # Slice fleet config
    fleet_config = distribution[[hex_column, "cars", "EVs", "AVs"]]

    return fleet_config


def generate_mixed_ride_hailing_fleet(env, fleet_config):
    """
    Generate a mixed shared vehicle fleet based on given fleet config.
    :param env: SimPy Environment (passed to vehicles)
    :param fleet_config: DataFrame with following 5 columns hex_id, cars, scooters, kick_scooters, bikes
    :return: MixedSharedVehicleFleet Object
    """
    # New Fleet Object
    fleet = MixedRideHailingFleet(env)

    # Access to underlying geodesic environment
    geo_env = GeodesicEnvironment.getInstance()

    # Get Column Identifier for current resolution (e.g., hex_id_7)
    hex_column = Configuration.instance().spatial_resolution_column

    # Global Config File (values from config ini files)
    config = Configuration.instance()

    # Load Vehicle Configurations
    c_config = config.get_vehicle_config("SharedCar")

    for index, row in fleet_config.iterrows():
        # We need to spawn vehicles in this hexagon
        hex_id = row[hex_column]

        # We need to spawn vehicles according to
        car_count = row["cars"]
        EV_count = row["EVs"]
        AVs_count = row["AVs"]

        # Add EV Ridehailing
        for current_car in range(EV_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            car = RideHailingCar(
                env,
                pos,
                c_config.max_available_seats,
                c_config.max_state_of_charge,
                c_config.energy_consumption,
                c_config.velocity,
                c_config.price_per_min,
            )
            fleet.add_shared_vehicle(car)
            car._fleet = fleet

        # Add Regular Ridehailing
        for current_car in range(car_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            car = RideHailingCar(
                env,
                pos,
                c_config.max_available_seats,
                c_config.max_state_of_charge,
                c_config.energy_consumption,
                c_config.velocity,
                c_config.price_per_min,
                electric_vehicle=False,
            )
            fleet.add_shared_vehicle(car)
            car._fleet = fleet

        # Add AVs
        for current_AV in range(AVs_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            autonomous_car = AutonomousCar(
                env,
                pos,
                c_config.max_available_seats,
                c_config.max_state_of_charge,
                c_config.energy_consumption,
                c_config.velocity,
                c_config.price_per_min,
            )
            fleet.add_shared_vehicle(autonomous_car)
            autonomous_car._fleet = fleet

    return fleet


def generate_mixed_fleet(env, fleet_config):
    """
    Generate a mixed shared vehicle fleet based on given fleet config.
    :param env: SimPy Environment (passed to vehicles)
    :param fleet_config: DataFrame with following 5 columns hex_id, cars, scooters, kick_scooters, bikes
    :return: MixedSharedVehicleFleet Object
    """
    # New Fleet Object
    fleet = MixedSharedVehicleFleet(env)

    # Access to underlying geodesic environment
    geo_env = GeodesicEnvironment.getInstance()

    # Get Column Identifier for current resolution (e.g., hex_id_7)
    hex_column = Configuration.instance().spatial_resolution_column

    # Global Config File (values from config ini files)
    config = Configuration.instance()

    # Load Vehicle Configurations
    c_config = config.get_vehicle_config("SharedCar")
    s_config = config.get_vehicle_config("SharedScooter")
    ks_config = config.get_vehicle_config("SharedKickScooter")
    b_config = config.get_vehicle_config("SharedBike")

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
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            car = SharedCar(
                env,
                pos,
                c_config.max_available_seats,
                c_config.max_state_of_charge,
                c_config.energy_consumption,
                c_config.velocity,
                c_config.price_per_min,
            )
            fleet.add_shared_vehicle(car)

        # Add Scooter
        for current_scooter in range(scooter_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            scooter = SharedScooter(
                env,
                pos,
                s_config.max_available_seats,
                s_config.max_state_of_charge,
                s_config.energy_consumption,
                s_config.velocity,
                s_config.price_per_min,
            )
            fleet.add_shared_vehicle(scooter)

        # Add Kick Scooter
        for current_kick_scooter in range(kick_scooter_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            kick_scooter = SharedKickScooter(
                env,
                pos,
                ks_config.max_available_seats,
                ks_config.max_state_of_charge,
                ks_config.energy_consumption,
                ks_config.velocity,
                ks_config.price_per_min,
            )
            fleet.add_shared_vehicle(kick_scooter)

        for current_bike in range(bike_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)

            bike = SharedBike(
                env,
                pos,
                b_config.max_available_seats,
                b_config.velocity,
                b_config.price_per_min,
            )
            fleet.add_shared_vehicle(bike)

    return fleet
