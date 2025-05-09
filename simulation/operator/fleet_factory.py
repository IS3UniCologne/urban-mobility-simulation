import pandas as pd
import simpy

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import VehicleMode
from simulation.helper.random.random_manager import RandomManager
from simulation.operator.mixed_ride_hailing_fleet import MixedRideHailingFleet
from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
from simulation.vehicle.ride_hailing_AV import RideHailingAV
from simulation.vehicle.ride_hailing_car import RideHailingCar
from simulation.vehicle.shared_vehicle import SharedVehicle

rng = RandomManager().get_rng(component_name="FLEETFACTORY")


def generate_fleet_config(
    distribution: pd.DataFrame,
    n_cars: int = 1000,
    n_scooter: int = 500,
    n_kick_scooter: int = 500,
    n_bikes: int = 500,
) -> pd.DataFrame:
    """
    Calculate vehicle distribution based on activity distribution per mode.

    Input Distribution generated using Script: Prepare_Vehicle_Supply_Data
    :param distribution: DataFrame consisting of five columns ["hex_id", "cars_prob", "scooters_prob", "kick_scooters_prob", "bikes_prob"]
    :return: Fleet Configuration (i.e., where are how many vehciles distributed)
    """

    # Sample Supply Distribution for Cars
    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        rng.multinomial(n_cars, cars_prob_arr, size=1).transpose(),
        columns=["car_count"],
    )
    car_cnt.index = distribution.index
    distribution["cars"] = car_cnt["car_count"]

    # Sample Supply Distribution for Cars
    scooters_prob_arr = distribution["scooters_prob"].to_numpy()
    scooters_cnt = pd.DataFrame(
        rng.multinomial(n_scooter, scooters_prob_arr, size=1).transpose(),
        columns=["scooters_count"],
    )
    scooters_cnt.index = distribution.index
    distribution["scooters"] = scooters_cnt["scooters_count"]

    # Sample Supply Distribution for Cars
    kick_scooters_prob_arr = distribution["kick_scooters_prob"].to_numpy()
    kick_scooters_cnt = pd.DataFrame(
        rng.multinomial(n_kick_scooter, kick_scooters_prob_arr, size=1).transpose(),
        columns=["kick_scooters_count"],
    )
    kick_scooters_cnt.index = distribution.index
    distribution["kick_scooters"] = kick_scooters_cnt["kick_scooters_count"]

    # Sample Supply Distribution for Cars
    bikes_prob_arr = distribution["bikes_prob"].to_numpy()
    bikes_cnt = pd.DataFrame(
        rng.multinomial(n_bikes, bikes_prob_arr, size=1).transpose(),
        columns=["bikes_count"],
    )
    bikes_cnt.index = distribution.index
    distribution["bikes"] = bikes_cnt["bikes_count"]

    hex_column = Configuration().world.SPATIAL_RESOLUTION_COLUMN

    # Slice fleet config
    fleet_config = distribution[
        [hex_column, "cars", "scooters", "kick_scooters", "bikes"]
    ]

    return fleet_config


def generate_ridehailing_fleet_config(
    distribution: pd.DataFrame,
    n_cars: int = 1000,
    n_AVs: int = 500,  # TODO: This is completely ignored/overwritten. Either remov or change calculation below
) -> pd.DataFrame:
    """
    Calculate vehicle distribution based on activity distribution per mode.

    Input Distribution generated using Script: Prepare_Vehicle_Supply_Data
    :param distribution: DataFrame consisting of five columns ["hex_id", "cars_prob", "scooters_prob", "kick_scooters_prob", "bikes_prob"]
    :return: Fleet Configuration (i.e., where are how many vehciles distributed)
    """

    config = Configuration()
    EV_peneteration = config.ride_hailing_global.EV_PENETRATION
    AV_peneteration = config.ride_hailing_global.AV_PENETRATION
    n_AVs = int(AV_peneteration * n_cars)
    n_non_AVs = int((1 - AV_peneteration) * n_cars)
    n_EVs = int(EV_peneteration * n_non_AVs)
    n_cars = int((1 - EV_peneteration) * n_non_AVs)

    # Sample Supply Distribution for Cars
    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        rng.multinomial(n_cars, cars_prob_arr, size=1).transpose(),
        columns=["car_count"],
    )
    car_cnt.index = distribution.index
    distribution["cars"] = car_cnt["car_count"]

    # Sample Supply Distribution for Cars
    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        rng.multinomial(n_EVs, cars_prob_arr, size=1).transpose(), columns=["car_count"]
    )
    car_cnt.index = distribution.index
    distribution["EVs"] = car_cnt["car_count"]

    cars_prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        rng.multinomial(n_AVs, cars_prob_arr, size=1).transpose(), columns=["car_count"]
    )
    car_cnt.index = distribution.index
    distribution["AVs"] = car_cnt["car_count"]

    # Sample Supply Distribution for Cars
    hex_column = Configuration().world.SPATIAL_RESOLUTION_COLUMN

    # Slice fleet config
    fleet_config = distribution[[hex_column, "cars", "EVs", "AVs"]]

    return fleet_config


def generate_AV_fleet(
    env: simpy.Environment, distribution: pd.DataFrame, n: int = 500
) -> MixedRideHailingFleet:
    config = Configuration()
    av_config = config.ride_hailing_vehicles["AutonomousCar"]

    # Sample Supply Distribution for Cars
    prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        rng.multinomial(n, prob_arr, size=1).transpose(), columns=["car_count"]
    )
    car_cnt.index = distribution.index
    distribution["AVs"] = car_cnt["car_count"]

    hex_column = Configuration().world.SPATIAL_RESOLUTION_COLUMN

    # Slice fleet config
    fleet_config = distribution[[hex_column, "AVs"]]

    # New Fleet Object
    fleet = MixedRideHailingFleet(env)

    # Access to underlying geodesic environment
    geo_env = GeodesicEnvironment.getInstance()

    for _index, row in fleet_config.iterrows():
        # We need to spawn vehicles in this hexagon
        hex_id = row[hex_column]
        count = row["AVs"]

        # Add AVs
        for _current_AV in range(count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            RideHailingAV(
                env=env,
                position=pos,
                fleet=fleet,
                velocity=av_config.VELOCITY,
                max_available_seats=av_config.MAX_AVAILABLE_SEATS,
                max_state_of_charge=av_config.MAX_STATE_OF_CHARGE,
                energy_consumption=av_config.ENERGY_CONSUMPTION,
                price_per_min=av_config.PRICE_PER_MIN,
            )

    return fleet


def generate_mixed_ride_hailing_fleet(
    env: simpy.Environment, fleet_config: pd.DataFrame
) -> MixedRideHailingFleet:
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
    hex_column = Configuration().world.SPATIAL_RESOLUTION_COLUMN

    # Global Config File (values from config ini files)
    config = Configuration()

    # Load Vehicle Configurations
    rh_config = config.ride_hailing_vehicles["RideHailingCar"]
    av_config = config.ride_hailing_vehicles["AutonomousCar"]

    for _index, row in fleet_config.iterrows():
        # We need to spawn vehicles in this hexagon
        hex_id = row[hex_column]

        # We need to spawn vehicles according to
        car_count = row["cars"]
        EV_count = row["EVs"]
        AVs_count = row["AVs"]

        # Add EV Ridehailing
        for _current_car in range(EV_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            RideHailingCar(
                env=env,
                position=pos,
                fleet=fleet,
                velocity=rh_config.VELOCITY,
                max_available_seats=rh_config.MAX_AVAILABLE_SEATS,
                max_state_of_charge=rh_config.MAX_STATE_OF_CHARGE,
                energy_consumption=rh_config.ENERGY_CONSUMPTION,
                price_per_min=rh_config.PRICE_PER_MIN,
            )

        # Add Regular Ridehailing
        for _current_car in range(car_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            RideHailingCar(
                env=env,
                fleet=fleet,
                position=pos,
                velocity=rh_config.VELOCITY,
                max_available_seats=rh_config.MAX_AVAILABLE_SEATS,
                max_state_of_charge=rh_config.MAX_STATE_OF_CHARGE,
                energy_consumption=rh_config.ENERGY_CONSUMPTION,
                price_per_min=rh_config.PRICE_PER_MIN,
                is_electric=False,
            )

        # Add AVs
        for _current_AV in range(AVs_count):
            rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)
            RideHailingAV(
                env=env,
                fleet=fleet,
                position=pos,
                velocity=av_config.VELOCITY,
                max_available_seats=av_config.MAX_AVAILABLE_SEATS,
                max_state_of_charge=av_config.MAX_STATE_OF_CHARGE,
                energy_consumption=av_config.ENERGY_CONSUMPTION,
                price_per_min=av_config.PRICE_PER_MIN,
            )

    return fleet


def generate_mixed_fleet(
    env: simpy.Environment, fleet_config: pd.DataFrame
) -> MixedSharedVehicleFleet:
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
    hex_column = Configuration().world.SPATIAL_RESOLUTION_COLUMN

    # Global Config File (values from config ini files)
    config = Configuration()

    # TODO: Once the fleetconfig uses VehicleMode enums, we can directly iterate over the modes
    # Define vehicle types and their configuration
    vehicle_types = {
        "cars": VehicleMode.Car,
        "scooters": VehicleMode.Scooter,
        "kick_scooters": VehicleMode.KickScooter,
        "bikes": VehicleMode.Bike,
    }

    # Process each hexagon in the fleet config
    for _index, row in fleet_config.iterrows():
        # Get hexagon ID
        hex_id = row[hex_column]

        # Create vehicles for each type
        for count_column, vehicle_mode in vehicle_types.items():
            vehicle_count = row[count_column]
            vehicle_config = config.shared_vehicles[vehicle_mode]

            # Create the specified number of vehicles
            for _ in range(vehicle_count):
                # Get random position within hexagon
                rdm_lat, rdm_lng = geo_env.get_random_position(hex_id)
                pos = GeodesicPosition(rdm_lat, rdm_lng, hex_id)

                # Create vehicle
                SharedVehicle(
                    env=env,
                    fleet=fleet,
                    position=pos,
                    velocity=vehicle_config.VELOCITY,
                    vehicle_mode=vehicle_mode,
                    max_available_seats=vehicle_config.MAX_AVAILABLE_SEATS,
                    max_state_of_charge=vehicle_config.MAX_STATE_OF_CHARGE,
                    energy_consumption=vehicle_config.ENERGY_CONSUMPTION,
                    price_per_min=vehicle_config.PRICE_PER_MIN,
                )

    return fleet
