from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleType
from simulation.operator.mixed_ride_hailing_fleet import MixedRideHailingFleet
from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
from simulation.vehicle.ride_hailing_AV import RideHailingAV
from simulation.vehicle.ride_hailing_car import RideHailingCar
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.world.world import World


def generate_fleet_config(sim: SimulationContext) -> pd.DataFrame:
    """
    Calculate vehicle distribution based on activity distribution per mode.

    Input Distribution generated using Script: Prepare_Vehicle_Supply_Data
    :param sim: SimulationContext containing config and random manager
    :return: Fleet Configuration (i.e., where are how many vehciles distributed)
    """
    # TODO make this operator specific
    config = sim.config
    random_manager = sim.random_manager

    n_cars = config.operators[0].N_VEHICLES[VehicleType.CAR]
    n_scooter = config.operators[0].N_VEHICLES[VehicleType.SCOOTER]
    n_kick_scooter = config.operators[0].N_VEHICLES[VehicleType.KICK_SCOOTER]
    n_bikes = config.operators[0].N_VEHICLES[VehicleType.BIKE]

    supply_path = config.path.PATH_VEHICLE_SUPPLY
    distribution = pd.read_csv(supply_path)

    rng = random_manager.get_rng(component_name="FLEETFACTORY")

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

    hex_column = config.world.SPATIAL_RESOLUTION.column_name

    # Slice fleet config
    fleet_config = distribution[
        [hex_column, "cars", "scooters", "kick_scooters", "bikes"]
    ]

    return fleet_config


def generate_ridehailing_fleet_config(sim: SimulationContext) -> pd.DataFrame:
    """
    Calculate vehicle distribution based on activity distribution per mode.

    Input Distribution generated using Script: Prepare_Vehicle_Supply_Data
    :param sim: SimulationContext containing config and random manager
    :return: Fleet Configuration (i.e., where are how many vehicles distributed)
    """
    config = sim.config

    supply_path = config.path.PATH_VEHICLE_SUPPLY
    distribution = pd.read_csv(supply_path)

    rng = sim.random_manager.get_rng(component_name="FLEETFACTORY")

    n_cars = config.ride_hailing_global.N_RIDE_HAILING_CARS
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
    hex_column = config.world.SPATIAL_RESOLUTION.column_name

    # Slice fleet config
    fleet_config = distribution[[hex_column, "cars", "EVs", "AVs"]]

    return fleet_config


def generate_AV_fleet(
    sim: SimulationContext, world: World, distribution: pd.DataFrame, n: int
) -> MixedRideHailingFleet:
    rng = sim.random_manager.get_rng(component_name="FLEETFACTORY")

    av_config = sim.config.ride_hailing_vehicles["AutonomousCar"]

    # Sample Supply Distribution for Cars
    prob_arr = distribution["cars_prob"].to_numpy()
    car_cnt = pd.DataFrame(
        rng.multinomial(n, prob_arr, size=1).transpose(), columns=["car_count"]
    )
    car_cnt.index = distribution.index
    distribution["AVs"] = car_cnt["car_count"]

    hex_column = sim.config.world.SPATIAL_RESOLUTION.column_name

    # Slice fleet config
    fleet_config = distribution[[hex_column, "AVs"]]

    # New Fleet Object
    fleet = MixedRideHailingFleet(sim=sim, world=world)

    for _index, row in fleet_config.iterrows():
        # We need to spawn vehicles in this hexagon
        hex_id = row[hex_column]
        count = row["AVs"]

        # Add AVs
        for _current_AV in range(count):
            rdm_lat, rdm_lng = sim.geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(sim, rdm_lat, rdm_lng, hex_id)
            RideHailingAV(sim=sim, position=pos, fleet=fleet, vehicle_config=av_config)

    return fleet


def generate_mixed_ride_hailing_fleet(
    sim: SimulationContext, world: World
) -> MixedRideHailingFleet:
    """
    Generate a mixed ride hailing fleet based on fleet config.
    :param sim: SimulationContext containing all necessary components
    :return: MixedRideHailingFleet Object
    """

    fleet_config = generate_ridehailing_fleet_config(sim=sim)

    # New Fleet Object
    fleet = MixedRideHailingFleet(sim=sim, world=world)

    # Get Column Identifier for current resolution (e.g., hex_id_7)
    hex_column = sim.config.world.SPATIAL_RESOLUTION.column_name

    # Load Vehicle Configurations
    rh_config = sim.config.ride_hailing_vehicles["RideHailingCar"]
    av_config = sim.config.ride_hailing_vehicles["AutonomousCar"]

    for _index, row in fleet_config.iterrows():
        # We need to spawn vehicles in this hexagon
        hex_id = row[hex_column]

        # We need to spawn vehicles according to
        car_count = row["cars"]
        EV_count = row["EVs"]
        AVs_count = row["AVs"]

        # Add EV Ridehailing
        for _current_car in range(EV_count):
            rdm_lat, rdm_lng = sim.geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(sim, rdm_lat, rdm_lng, hex_id)
            RideHailingCar(sim=sim, position=pos, fleet=fleet, vehicle_config=rh_config)

        # Add Regular Ridehailing
        for _current_car in range(car_count):
            rdm_lat, rdm_lng = sim.geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(sim, rdm_lat, rdm_lng, hex_id)
            RideHailingCar(sim=sim, fleet=fleet, position=pos, vehicle_config=rh_config)

        # Add AVs
        for _current_AV in range(AVs_count):
            rdm_lat, rdm_lng = sim.geo_env.get_random_position(hex_id)
            pos = GeodesicPosition(sim, rdm_lat, rdm_lng, hex_id)
            RideHailingAV(sim=sim, fleet=fleet, position=pos, vehicle_config=av_config)

    return fleet


def generate_mixed_fleet(
    sim: SimulationContext, world: World
) -> MixedSharedVehicleFleet:
    """
    Generate a mixed shared vehicle fleet based on given fleet config.
    :param sim: SimulationContext containing all necessary components
    :return: MixedSharedVehicleFleet Object
    """

    fleet_config = generate_fleet_config(sim=sim)
    # New Fleet Object
    fleet = MixedSharedVehicleFleet(sim=sim, world=world)

    # Get Column Identifier for current resolution (e.g., hex_id_7)
    hex_column = sim.config.world.SPATIAL_RESOLUTION.column_name

    # TODO: This should not be hardcoded
    # Define vehicle types and their configuration
    vehicle_types = {
        "cars": VehicleType.CAR,
        "scooters": VehicleType.SCOOTER,
        "kick_scooters": VehicleType.KICK_SCOOTER,
        "bikes": VehicleType.BIKE,
    }

    # Process each hexagon in the fleet config
    for _index, row in fleet_config.iterrows():
        # Get hexagon ID
        hex_id = row[hex_column]

        # Create vehicles for each type
        for count_column, vehicle_mode in vehicle_types.items():
            vehicle_count = row[count_column]
            vehicle_config = sim.config.shared_vehicles[vehicle_mode]

            # Create the specified number of vehicles
            for _ in range(vehicle_count):
                # Get random position within hexagon
                rdm_lat, rdm_lng = sim.geo_env.get_random_position(hex_id)
                pos = GeodesicPosition(sim, rdm_lat, rdm_lng, hex_id)

                # Create vehicle
                SharedVehicle(
                    sim=sim, fleet=fleet, position=pos, vehicle_config=vehicle_config
                )

    return fleet
