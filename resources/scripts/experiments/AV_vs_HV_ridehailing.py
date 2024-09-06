# from pqdm.processes import pqdm
import logging
import os
import sys
from configparser import ConfigParser
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import simpy

import utils
from simulation.agent.user import (
    User,  # must come before DemandFactory, otherwise circular imports
)
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    Configuration,
    ModeChoiceConfig,
    PopulationConfig,
    RideHailingOperatorConfig,
    RideHailingVehicleConfig,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.operator.fleet_factory import (
    generate_mixed_ride_hailing_fleet,
    generate_ridehailing_fleet_config,
)
from simulation.operator.operations_management.ridehailing_charging_operations import (
    RideHailingChargingOperations,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.vehicle.ride_hailing_AV import RideHailingAV
from simulation.vehicle.ride_hailing_car import RideHailingCar
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import (
    OnlyCarVehicleChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking

pd.set_option("display.max_columns", None)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Configuration from ini file.       #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


# Change working directory to path of main.py
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

# World Config
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
city = parser.get("WORLD", "city")

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# RideHailing Fleet Configuration         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Initialize config for different vehicle types
for idx, vehicle_type in enumerate(["AUTONOMOUS_CAR", "RIDEHAILING_CAR"]):
    vehicle_type_classes = ["AutonomousCar", "RideHailingCar"]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC")
    charging_cost_per_kWh = parser.getfloat(vehicle_type, "CHARGING_COST_PER_KWH")
    cost_per_km = parser.getfloat(vehicle_type, "COST_PER_KM")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")
    EV_relative_energy_consumption = parser.getfloat(
        vehicle_type, "EV_RELATIVE_ENERGY_CONSUMPTION"
    )

    rvc = RideHailingVehicleConfig(
        price_per_min=price_per_min,
        max_state_of_charge=max_state_of_charge,
        energy_consumption=energy_consumption,
        velocity=velocity,
        max_available_seats=max_available_seats,
        initial_SoC=initial_SoC,
        charging_cost_per_kWh=charging_cost_per_kWh,
        cost_per_km=cost_per_km,
        daily_total_cost=daily_total_cost,
        EV_relative_energy_consumption=EV_relative_energy_consumption,
    )
    global_config.add_ridehailing_vehicle_config(vehicle_type_classes[idx], rvc)

# Number of ridehailing cars in the fleet
n_ridehailing_cars = parser.getint("RIDE_HAILING", "n_ridehailing_cars")
# Number of autonomous cars in the fleet
n_autonomous_cars = parser.getint("RIDE_HAILING", "n_autonomous_cars")
# Not sure what this is for
allocation = parser.get("RIDE_HAILING", "ALLOCATION")
AV_price_reduction = parser.getfloat("RIDE_HAILING", "AV_PRICE_REDUCTION")
discount_rate = parser.getint("RIDE_HAILING", "DISCOUNT_RATE")

AV_penetration = parser.getfloat("SUPPLY", "AV_penetration")
EV_penetration = parser.getfloat("SUPPLY", "EV_penetration")
# Drivers share of the revenue made with each ride
driver_payment_share = parser.getfloat("RIDE_HAILING", "DRIVER_PAYMENT_SHARE")
price_params = parser.get("RIDE_HAILING", "PRICE_PARAMS")
price_params = price_params.split(",")
price_params = [float(x) * (1 - discount_rate) for x in price_params]
# Maximumn pickuo distance that is ok for the users
distance_threshold = parser.getfloat("RIDE_HAILING", "MAX_PICKUP_DISTANCE")
global_config.add_distance_threshold_to_user(distance_threshold)
# Vehicles whose state of charge is below the threshold value are to be charged
recharge_threshold = parser.get("RIDE_HAILING_OPERATOR", "RECHARGE_THRESHOLD").split(
    ","
)
recharge_threshold = [float(x) / 100 for x in recharge_threshold]

number_of_charging_locations = parser.getint(
    "CHARGING_INFRASTRUCTURE", "NUMBER_OF_CHARGING_STATIONS"
)
# Locations are defined as hexagons (regions) in the city
charging_station_locations = utils.parse_multiline_list(
    "CHARGING_INFRASTRUCTURE", "LOCATIONS", delimiter=","
)
charging_station_locations = charging_station_locations[:number_of_charging_locations]

charging_station_power = utils.parse_multiline_list(
    "CHARGING_INFRASTRUCTURE", "CHARGING_STATION_POWER", delimiter=",", cast=float
)
if len(charging_station_power) == 1:
    charging_station_power = list(
        np.full(number_of_charging_locations, charging_station_power[0])
    )

# Capacity is the number of charging stations in the charging hub (or plugs at a station)
charging_station_capacity = utils.parse_multiline_list(
    "CHARGING_INFRASTRUCTURE", "CHARGING_STATION_CAPACITY", delimiter=",", cast=int
)
if len(charging_station_capacity) == 1:
    charging_station_capacity = list(
        np.full(number_of_charging_locations, charging_station_capacity[0])
    )
operations_start = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint(
    "RIDE_HAILING_OPERATOR", "VEHICLE_RELOCATION_VELOCITY"
)

# Read drivers availability distribution
drivers_availability = parser.get("SUPPLY", "RH_availability").split(",")
drivers_availability = [
    round(float(x) * n_ridehailing_cars * (1 - AV_penetration))
    for x in drivers_availability
]
available_modes = parser.get("RIDE_HAILING", "available_vehicle_modes_ridehailing")
available_modes = available_modes.split(",")
available_modes_supply = [n_ridehailing_cars, n_autonomous_cars]

rhoc = RideHailingOperatorConfig(
    recharge_threshold=recharge_threshold,
    operations_start=operations_start,
    operations_duration=operations_duration,
    vehicle_relocation_velocity=vehicle_relocation_velocity,
    available_modes=available_modes,
    available_modes_supply=available_modes_supply,
    n_autonomous_cars=n_autonomous_cars,
    n_ridehailing_cars=n_ridehailing_cars,
    allocation=allocation,
)

global_config.add_ridehailing_operator_config(rhoc)
global_config.add_tech_penetration(EV_penetration, AV_penetration)
global_config.add_driver_availability_vector(drivers_availability)
global_config.add_ride_hailing_info(
    driver_payment_share, AV_price_reduction, price_params
)

###### End RideHailing Fleet Configuration ######

# A score that represents how much users trust autonomous vehicles. Not relevant for every simulation
AV_trust = parser.get("MODE_CHOICE_MODEL", "AV_trust").split(",")
AV_trust = [float(x) for x in AV_trust]

global_config.add_AV_trust(AV_trust)

#### Population Configuration ####

population_probabilities = parser.get("RIDE_HAILING", "population_probabilities").split(
    ","
)
population_probabilities = [float(x) for x in population_probabilities]

type_paths = parser.get("POPULATION", "type_paths")

pc = PopulationConfig(population_probabilities, type_paths)

global_config.add_population_config(pc)

##### Mode Choice Config (largely unecessary) #####
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")

# Initialize the mode choice config
mc = ModeChoiceConfig(
    mode_choice_strategy, mode_choice_sub_boundary, mode_choice_model_path
)

# Load the config to the global config
global_config.add_mode_choice_config(mc)

# Output Configuration
store_results = parser.getboolean("OUTPUT", "persist_results")
store_results = parser.getboolean("OUTPUT", "persist_results")
output_folder = parser.get("OUTPUT", "output_folder")
transaction_file = parser.get("OUTPUT", "transaction_file")
fleet_state_file = parser.get("OUTPUT", "fleet_state_file")

global_config.set_store_results(store_results)
global_config.set_output_path(output_folder)
global_config.set_transaction_file(transaction_file)
global_config.set_fleet_state_file(fleet_state_file)

# Log Level
log_level = parser.get("SETTINGS", "log_level")

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Configure Logging.                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)

logger = logging.getLogger()
logger.setLevel(log_level)

# Add Custom Init Filters (which work without the ENV obj)
cf_init = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf_init)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s"
)
file_handler = logging.FileHandler("report.log")
file_handler.setFormatter(formatter)
file_handler.setLevel(log_level)

# Add Custom Init Filters (which work without the ENV obj)
cf_init = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf_init)

# # Set the basic configuration
# log_level = logging.INFO
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)20s] [%(clazz)30s %(oid)3s]: %(message)s',
#                     datefmt='%m/%d/%Y %I:%M:%S %p')

# # Set the logger level
# logger.setLevel(log_level)

# # Block Logger of third party software
# logging.getLogger("fiona").setLevel(logging.WARNING)

# # Set up file handler with formatter
# formatter = logging.Formatter('%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s')
# file_handler = logging.FileHandler('report.log')
# file_handler.setFormatter(formatter)
# file_handler.setLevel(log_level)

# # Add file handler to the logger
# logger.addHandler(file_handler)

print("Basic config initialized")

# logger.addHandler(file_handler)


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Underlying Spatial Environment.    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


def load_environment():
    # Read Environment Files
    filename = bounding_box_path
    with open(filename) as file:
        env_df = gpd.read_file(file)

    filename = env_layer_hex_9
    with open(filename) as file:
        env_df_hex_9 = gpd.read_file(file, driver="GeoJSON")
        env_df_hex_9.set_index("hex_id_9", inplace=True)

    filename = env_layer_hex_8
    with open(filename) as file:
        env_df_hex_8 = gpd.read_file(file)
        env_df_hex_8.set_index("hex_id_8", inplace=True)

    filename = env_layer_hex_7
    with open(filename) as file:
        env_df_hex_7 = gpd.read_file(file)
        env_df_hex_7.set_index("hex_id_7", inplace=True)

    geodesic_environment = GeodesicEnvironment()
    geodesic_environment.addLayer("bounding_box", env_df)
    geodesic_environment.addLayer("hex_9", env_df_hex_9)
    geodesic_environment.addLayer("hex_8", env_df_hex_8)
    geodesic_environment.addLayer("hex_7", env_df_hex_7)

    return geodesic_environment


# Load Spatial Environment
load_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Demand Data (once).                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

p = Path(demand_file_path)
di = DemandImporter(
    spatial_resolution=global_config.spatial_resolution,
    temporal_resolution=global_config.temporal_resolution,
    daily_resolution=global_config.daily_resolution,
    city=global_config.city,
)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(f"hex_{spatial_res}").index.tolist()
dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure", city)
distance_matrix = dmi.load_distance_matrix()


def run_single_simulation(
    start_time=0,
    end_time=20,
    n_cars=500,
    seed=42,
    phase=1,
    AV_trust=AV_trust,
    pop_prob=population_probabilities,
    allocation=None,
    EV_penetration=1,
    AV_penetration=1,
    returnDataFrame=False,
    charging_capacity=20,
    charging_power=50,
    AV_price_reduction=None,
    discount_rate=0,
    MoD_interval_reduction=0,
    mode_choice_strategy=mode_choice_strategy,
):
    """
    :param price_params_ride_hailing:
    :param AV_trust:
    :param EV_penetration:
    :param allocation:
    :param charging_capacity:
    :param charging_power:
    :param AV_price_reduction:
    :param start_time:
    :param end_time:
    :param n_cars:
    :param n_scooter:
    :param n_kick_scooter:
    :param seed:
    :param substitution:
    :param pop_prob: 1.0 means only price sensitive users, 0.0 means only sustainable users
    :return:
    """
    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Setup Simulation Environment.           #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Simulation Environment
    env = simpy.Environment(initial_time=start_time)

    # Before each simulation run, reset counter and random number generators
    RideHailingCar.ride_hailing_car_id = 0
    RideHailingAV.ride_hailing_av_id = 0
    User.user_id = 0
    DemandFactory.counter = 0

    GeodesicEnvironment.getInstance().reset_random_generator(seed)

    # Inject Simulation Environment to Logger (such that we can log the env time)
    cf = SimulationContextFilter(filter_name="add_env", extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. Simulation Modules.               #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Read ride-hailing related parameters
    if not AV_price_reduction:
        AV_price_reduction = parser.getfloat("RIDE_HAILING", "AV_PRICE_REDUCTION")
    price_params_ride_hailing = parser.get("RIDE_HAILING", "PRICE_PARAMS")
    price_params_ride_hailing = price_params_ride_hailing.split(",")
    price_params_ride_hailing = [
        float(x) * (1 - discount_rate) for x in price_params_ride_hailing
    ]
    global_config.add_ride_hailing_info(
        driver_payment_share, AV_price_reduction, price_params_ride_hailing
    )
    distance_threshold_to_user = parser.getfloat("RIDE_HAILING", "MAX_PICKUP_DISTANCE")
    global_config.add_distance_threshold_to_user(distance_threshold_to_user)

    # Technology penetration
    global_config.add_tech_penetration(EV_penetration, AV_penetration)
    global_config.add_AV_trust(AV_trust)

    # Read drivers availability distribution
    drivers_availability = parser.get("SUPPLY", "RH_availability").split(",")
    drivers_availability = [
        round(float(x) * n_cars * (1 - AV_penetration)) for x in drivers_availability
    ]
    global_config.add_driver_availability_vector(drivers_availability)

    # Vehicle Choice Model
    if mode_choice_strategy == "substitution":
        vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
            ["RideHailingCar", "AutonomousCar"]
        )

    else:
        raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

    # Population Type
    population_factory = PopulationFactory(pop_prob, seed)

    # Charging Infrastructure
    number_of_charging_locations = parser.getint(
        "CHARGING_INFRASTRUCTURE", "NUMBER_OF_CHARGING_STATIONS"
    )
    charging_location_list = utils.parse_multiline_list(
        "CHARGING_INFRASTRUCTURE", "LOCATIONS", delimiter=","
    )[:number_of_charging_locations]
    if isinstance(charging_power, list):
        charging_power_list = charging_power
    else:
        charging_power_list = list(np.full(len(charging_location_list), charging_power))
    if isinstance(charging_capacity, list):
        charging_capacity_list = charging_capacity
    else:
        charging_capacity_list = list(
            np.full(len(charging_location_list), charging_capacity)
        )
    sic = ChargingInfrastructureConfig(
        charging_location_list, charging_power_list, charging_capacity_list
    )
    global_config.add_charging_infrastructure_config(sic)
    charging_infrastructure = ChargingInfrastructure(
        env,
        charging_location_list,
        charging_power_list,
        charging_capacity_list,
        reset=True,
    )

    # Users
    ## What is "MoD_interval_reduction" for?
    global_config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Load Vehicle Fleet and Place on World.  #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    supply_prob = pd.read_csv(supply_file_path)

    ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(
        distribution=supply_prob,
        n_cars=n_cars,
        n_AVs=n_cars,
        allocation_method="historical",
        allocation=allocation,
    )
    ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(
        env, ride_hailing_fleet_config_0
    )

    ride_hailing_fleet_config_1 = generate_ridehailing_fleet_config(
        distribution=supply_prob,
        n_cars=n_cars,
        n_AVs=n_cars,
        allocation_method="historical",
        allocation=allocation,
    )
    ride_hailing_fleet_1 = generate_mixed_ride_hailing_fleet(
        env, ride_hailing_fleet_config_1
    )

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Operations Management Processes         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    available_vehicle_modes_ridehailing = ["RideHailingCar", "AutonomousCar"]
    available_vehicle_modes_supply_ride_hailing = [n_cars, n_cars]

    # Initialize Rule Based Relocation Scheduler
    # For RideHailing Fleets
    ridehailing_operations_0 = RideHailingChargingOperations(
        env=env,
        distance_matrix=distance_matrix,
        time_between_operations=global_config.ridehailing_operator_config.operations_start,
        operation_duration=global_config.ridehailing_operator_config.operations_duration,
        available_modes=available_vehicle_modes_ridehailing,
        available_modes_supply=available_vehicle_modes_supply_ride_hailing,
        state_of_charge_threshold=global_config.ridehailing_operator_config.recharge_threshold,
    )

    ridehailing_operations_1 = RideHailingChargingOperations(
        env=env,
        distance_matrix=distance_matrix,
        time_between_operations=global_config.ridehailing_operator_config.operations_start,
        operation_duration=global_config.ridehailing_operator_config.operations_duration,
        available_modes=available_vehicle_modes_ridehailing,
        available_modes_supply=available_vehicle_modes_supply_ride_hailing,
        state_of_charge_threshold=global_config.ridehailing_operator_config.recharge_threshold,
    )

    # Operator Modules
    search_engine = {
        "ride_hailing_0": RideHailingSearchEngine(env),
        "ride_hailing_1": RideHailingSearchEngine(env),
    }

    vehicle_assignment_engine = {
        "ride_hailing_0": RideHailingAllocationEngine(env),
        "ride_hailing_1": RideHailingAllocationEngine(env),
    }

    ridehailing_operator_0 = RideHailingOperator(
        env=env,
        fleet=ride_hailing_fleet_0,
        charging_infrastructure=charging_infrastructure,
        operations=ridehailing_operations_0,
        search_engine=search_engine["ride_hailing_0"],
        allocation_engine=vehicle_assignment_engine["ride_hailing_0"],
    )

    ridehailing_operator_1 = RideHailingOperator(
        env=env,
        fleet=ride_hailing_fleet_1,
        charging_infrastructure=charging_infrastructure,
        operations=ridehailing_operations_1,
        search_engine=search_engine["ride_hailing_1"],
        allocation_engine=vehicle_assignment_engine["ride_hailing_1"],
    )

    payment_engine = {
        "ride_hailing_0": ridehailing_operator_0,
        "ride_hailing_1": ridehailing_operator_1,
    }

    # World
    Tracking.init(env)
    world = World.init(
        env,
        search_engine,
        payment_engine,
        vehicle_assignment_engine,
        vehicle_choice_model,
        population_factory,
        charging_infrastructure,
        reset=True,
    )

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Spawn Demand Processes.                 #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    ride_hailing_demand_factory = DemandFactory(
        env, demand_profile, di, world, demand_modifier_paths, seed, mode="ride_hailing"
    )

    env.process(ride_hailing_demand_factory.generate_demand())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Run Simulation.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    env.run(until=end_time)

    logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})

    total_cost_per_day = {
        "ride_hailing_0": (
            global_config.get_ridehailing_vehicle_config(
                "RideHailingCar"
            ).daily_total_cost
            * AV_penetration
            * n_cars
        )
        * (end_time / 1440),
        "ride_hailing_1": (
            global_config.get_ridehailing_vehicle_config(
                "RideHailingCar"
            ).daily_total_cost
            * AV_penetration
            * n_cars
        )
        * (end_time / 1440),
    }

    # Daily Total Cost (CAPEX+OPEX) (cost derived from RevCalc excel in iCloud folder)
    no_vehicles_to_be_charged = {
        "ride_hailing_0": ride_hailing_fleet_0.count_vehicles_below_soc_level(
            global_config.ridehailing_operator_config.recharge_threshold
        ),
        "ride_hailing_1": ride_hailing_fleet_1.count_vehicles_below_soc_level(
            global_config.ridehailing_operator_config.recharge_threshold
        ),
    }

    total_operational_cost = {
        "ride_hailing_0": ride_hailing_fleet_0.get_operational_costs(),
        "ride_hailing_1": ride_hailing_fleet_1.get_operational_costs(),
    }

    # Final Objective Function for Heuristic Search
    func_objective = {
        "ride_hailing_0": ridehailing_operator_0.total_revenue
        - total_cost_per_day["ride_hailing_0"]
        - ridehailing_operator_0.total_missed_revenue
        - total_operational_cost["ride_hailing_0"],
        "ride_hailing_1": ridehailing_operator_1.total_revenue
        - total_cost_per_day["ride_hailing_1"]
        - ridehailing_operator_1.total_missed_revenue
        - total_operational_cost["ride_hailing_1"],
    }
    transactions = {
        "ride_hailing_0": ridehailing_operator_0.get_transactions(),
        "ride_hailing_1": ridehailing_operator_1.get_transactions(),
    }

    if store_results:
        transactions["ride_hailing_0"].to_csv(
            Path(
                output_folder,
                "ride_hailing_0_"
                + scenario_name
                + "_"
                + "phase_"
                + str(phase)
                + "_"
                + transaction_file,
            ),
            index=False,
        )
        transactions["ride_hailing_1"].to_csv(
            Path(
                output_folder,
                "ride_hailing_1_"
                + scenario_name
                + "_"
                + "phase_"
                + str(phase)
                + "_"
                + transaction_file,
            ),
            index=False,
        )

    if returnDataFrame:
        # Persist Results
        result = {
            "fleet_size": [n_cars],
            "charging_capacity": [charging_capacity],
            "charging_power": [charging_power],
            "pop_prob": [pop_prob],
            "AV_trust": [AV_trust],
            "AV_penetration": [AV_penetration],
            "AV_price_reduction": [AV_price_reduction],
            "MCA_adjuster": [MoD_interval_reduction],
            "discount_rate": [discount_rate],
            "seed": [seed],
            "phase": [phase],
            "total_revenue_ride_hailing": [ridehailing_operator_0.total_revenue],
            "total_cost_per_day_ride_hailing": [total_cost_per_day["ride_hailing_0"]],
            "total_operational_cost_per_day_ride_hailing": total_operational_cost[
                "ride_hailing_0"
            ],
            "total_profit_ride_hailing": [
                ridehailing_operator_0.total_revenue
                - total_cost_per_day["ride_hailing_0"]
                - total_operational_cost["ride_hailing_0"]
            ],
            "total_trips_ride_hailing": len(world.users),
            "total_fulfilled_trips_ride_hailing": [
                ridehailing_operator_0.total_fulfilled_trips
            ],
            "total_missed_trips_ride_hailing": [
                ridehailing_operator_0.total_missed_trips
            ],
            "total_missed_revenue_ride_hailing": [
                ridehailing_operator_0.total_missed_revenue
            ],
        }

        transactions = transactions["ride_hailing_0"]
        # Calculate performance indicators per mode
        indicators_per_mode = (
            transactions[transactions["selected_vehicle_mode"] != "None"]
            .groupby(["selected_vehicle_mode"])
            .agg(
                {
                    "price": "sum",
                    "duration": "sum",
                    "distance": "sum",
                    "energy_consumption": "sum",
                    "waiting_time": "sum",
                    "pick_up_time": "sum",
                }
            )
        )

        # Count Trips by Vehicle Type
        overall_rentals = pd.DataFrame(result)
        available_modes = [
            "RideHailingCar_True",
            "RideHailingCar_False",
            "AutonomousCar_True",
        ]
        for mode in available_modes:
            rentals = (
                transactions[transactions["selected_vehicle_mode"] == mode]
                .groupby("state")
                .agg({"RideHailingCar": "sum", "AutonomousCar": "sum"})
                .reset_index(drop=True)
            )
            rentals = rentals.add_prefix("{}_".format(mode))
            overall_rentals = pd.concat([overall_rentals, rentals], axis=1)
            # "RideHailingCar_True": "sum", "RideHailingCar_False": "sum", "AutonomousCar_True": "sum"
            # Prepare KPI per Mode (Distance, Duration, Revenue)
            try:
                kpi_for_mode = indicators_per_mode.loc[[mode]].reset_index(drop=True)
            except Exception:
                kpi_for_mode = pd.DataFrame(
                    pd.Series(
                        {
                            "price": 0,
                            "duration": 0,
                            "distance": 0,
                            "energy_consumption": 0,
                            "waiting_time": 0,
                            "pick_up_time": 0,
                        }
                    )
                ).transpose()
            kpi_for_mode.rename(
                columns={"price": "revenue"}, inplace=True
            )  # to avoid future confusion
            kpi_for_mode = kpi_for_mode.add_prefix("{}_".format(mode))
            overall_rentals = pd.concat([overall_rentals, kpi_for_mode], axis=1)

        return overall_rentals
    else:
        return (
            ridehailing_operator_0.total_revenue,
            total_cost_per_day["ride_hailing_0"],
            total_operational_cost["ride_hailing_0"],
            ridehailing_operator_0.total_revenue
            - total_cost_per_day["ride_hailing_0"]
            - total_operational_cost["ride_hailing_0"],
            ridehailing_operator_0.total_fulfilled_trips,
            ridehailing_operator_0.total_missed_trips,
            no_vehicles_to_be_charged["ride_hailing_0"],
            func_objective["ride_hailing_0"],
            ridehailing_operator_1.total_revenue,
            total_cost_per_day["ride_hailing_1"],
            total_operational_cost["ride_hailing_1"],
            ridehailing_operator_1.total_revenue
            - total_cost_per_day["ride_hailing_1"]
            - total_operational_cost["ride_hailing_1"],
            ridehailing_operator_1.total_fulfilled_trips,
            ridehailing_operator_1.total_missed_trips,
            no_vehicles_to_be_charged["ride_hailing_1"],
            func_objective["ride_hailing_1"],
        )


### Single Run

TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
USER_SHARES = [0.247, 0.237, 0.19, 0.325]
scenario_name = "single_P_analysis"
# AV_trust_analysis, population_analysis, fleet_size_analysis, charging_capacity_analysis, tech_phase_analysis
phase = 1

result = run_single_simulation(
    end_time=600,
    n_cars=100,
    seed=4711,
    phase=phase,
    pop_prob=USER_SHARES,
    EV_penetration=TECH_SHARE[phase],
    charging_power=charging_station_power,
    charging_capacity=charging_station_capacity,
    AV_penetration=TECH_SHARE[phase],
    returnDataFrame=False,
)


# TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
# USER_SHARES = [0.247, 0.237, 0.19, 0.325]
# random.seed(42)
# seeds = random.sample(range(1000), 10)
# scenario_name = "single_P_analysis"
# phase = 3
# for seed in seeds[1:]:
#     a = run_single_simulation(
#         end_time=1400 * 1,
#         n_cars=500,
#         seed=seed,
#         phase=phase,
#         pop_prob=USER_SHARES,
#         EV_penetration=TECH_SHARE[phase],
#         charging_capacity=5,
#         AV_penetration=TECH_SHARE[phase],
#         returnDataFrame=False,
#         charging_power=10,
#     )

#     print(a)

# Simulation Experiments
# Random Variables for our Monte Carlo Run


# random.seed(42)
# seeds = random.sample(range(1000), 10)

# # Store all simulation results in this data frame
# all_simulations = pd.DataFrame()
# sim_days = 1
# scenario_name = "single_P_analysis"
# # AV_trust_analysis, population_analysis, fleet_size_analysis, charging_capacity_analysis, tech_phase_analysis
# TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
# phases = [0, 1, 2, 3]

# # Real Run

# if __name__ == "__main__":
#     T = 1440 * sim_days
#
#     # single phase
#     for phase in range(0, 101, 5):
#         phase /= 100
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed,
#                          'phase': phase,
#                          'EV_penetration': phase,
#                          'AV_penetration': phase, 'returnDataFrame': True,
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

### This is for analysing different proportion of user population
# for pop_type in range(4):
#     for user_share in range(11):
#
#         POP_PROB = [(10 - user_share) / 3 * 0.1, (10 - user_share) / 3 * 0.1, (10 - user_share) / 3 * 0.1,
#                     (10 - user_share) / 3 * 0.1]
#         POP_PROB[pop_type] = user_share * 0.1
#         for phase in phases:
#             data = []
#             for idx, seed in enumerate(seeds):
#                 data.append({'end_time': T, 'seed': seed,
#                              'phase': phase, 'pop_prob': POP_PROB,
#                              'EV_penetration': TECH_SHARE[phase],
#                              'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
#             sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                            mp_context=mp.get_context('spawn'))
#             for i in range(len(sim_res)):
#                 all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#             logging.error("seed: {}, idx: {}".format(seed, idx),
#                           extra={"clazz": "main", "oid": ""})

# After each seed save
# all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

### This is for analysing different AV_trust values

# for a_1 in [2, 4, 6, 8]:
#     for a_2 in [2, 4, 6, 8]:
#         for a_3 in [2, 4, 6, 8]:
#             for a_4 in [2, 4, 6, 8]:
#                 AV_TRUST = [a_1, a_2, a_3, a_4]
#                 for phase in phases:
#                     data = []
#                     for idx, seed in enumerate(seeds):
#                         data.append({'end_time': T, 'seed': seed,
#                                      'phase': phase, "AV_trust": AV_TRUST,
#                                      'EV_penetration': TECH_SHARE[phase],
#                                      'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
#                     sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                                    mp_context=mp.get_context('spawn'))
#                     for i in range(len(sim_res)):
#                         all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#                     logging.error("seed: {}, idx: {}".format(seed, idx),
#                                   extra={"clazz": "main", "oid": ""})
#
#                     # After each seed save
#                     all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'),
#                                            index=False)

### This is for analysing different fleet sizes

# for fleet_size in [200, 300, 400, 500, 600, 700, 800, 1000]:
#     for phase in phases:
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
#                          'phase': phase,
#                          'EV_penetration': TECH_SHARE[phase],
#                          'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})

# After each seed save
# all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# # This is for analysing different charging power
# POP_PROB = SHARES[0]
# for fleet_size in [200, 300, 400, 500, 600, 700, 800, 1000]:
#     for charging_capacity in [1, 4, 5, 10, 20]:
#         for charging_power in [5, 10, 22, 50]:
#             for phase in phases:
#                 data = []
#                 for idx, seed in enumerate(seeds):
#                     data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
#                                  'phase': phase, 'pop_prob': POP_PROB,
#                                  'EV_penetration': TECH_SHARE[phase], "charging_capacity": charging_capacity,
#                                  'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True,
#                                  'charging_power': charging_power})
#                 sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                                mp_context=mp.get_context('spawn'))
#                 for i in range(len(sim_res)):
#                     all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#                 logging.error("seed: {}, idx: {}".format(seed, idx),
#                               extra={"clazz": "main", "oid": ""})
#
#                 # After each seed save
#                 all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)
#
# print("FINISHED")

# for pop_prob in [[1.0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]:
#     for phase in range(0, 101, 5):
#         phase /= 100
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed,
#                          'phase': phase, 'pop_prob': pop_prob,
#                          'EV_penetration': phase,
#                          'AV_penetration': phase, 'returnDataFrame': True,
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# AV_price
# for phase in [25,50,75,100]:
#     phase = phase/100
#     for AV_price_fraction in range(3, 10):
#         AV_price_fraction /= 10
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed, 'discount_rate': 0,
#                          'phase': phase, 'AV_price_reduction': AV_price_fraction,
#                          'EV_penetration': phase,
#                          'AV_penetration': phase, 'returnDataFrame': True
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# MCA_P
# for phase in [25,50,75,100]:
#     phase = phase/100
#     for MCA_reduction in range(0, 10):
#         MCA_reduction /= 10
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed, 'discount_rate': 0,
#                          'phase': phase,
#                          'EV_penetration': phase, 'MoD_interval_reduction': MCA_reduction,
#                          'AV_penetration': phase, 'returnDataFrame': True
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

### FS_UP
# for pop_prob in [[1.0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]:
#     for AVT in range(0, 10):
#         AV_TRUST = [AVT, AVT, AVT, AVT]
#         phase = 0.5
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed,
#                          'phase': phase, 'pop_prob': pop_prob,
#                          'EV_penetration': phase, 'AV_trust': AV_TRUST,
#                          'AV_penetration': phase, 'returnDataFrame': True,
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# print("FINISHED")
