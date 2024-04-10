from pathlib import Path

import numpy as np
import pandas as pd

from simulation.agent.user import User  # must come before DemandFactory, otherwise circular imports
from simulation.helper.configuration.configuration import Configuration, VehicleConfig, ModeChoiceConfig, \
    SharedVehicleOperatorConfig, ChargingInfrastructureConfig
from simulation.infrastructure.charging_stations.charging_infastructure import ChargingInfrastructure
from simulation.infrastructure.helper.distance_matrix_importer import DistanceMatrixImporter
from simulation.operator.fleet_factory import generate_fleet_config, generate_mixed_fleet
from simulation.operator.operations_management.operations import Operations
from simulation.operator.operations_management.relocation_scheduler import RelocationScheduler
from simulation.operator.operations_management.service_worker import ServiceWorker
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import OnlyCarVehicleChoiceBehavior
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World

pd.set_option('display.max_columns', None)
import simpy
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.operator.shared_vehicle_allocation_engine import SharedVehicleAllocationEngine
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
import geopandas as gpd
from tracking.tracking import Tracking

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Configuration from ini file.       #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

import sys
from configparser import ConfigParser
import os

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
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

# Read Shared Vehicle Config and add to Global Config File
for idx, vehicle_type in enumerate(["SHARED_CAR", "SHARED_SCOOTER", "SHARED_KICK_SCOOTER", "SHARED_BIKE"]):
    vehicle_type_classes = ["SharedCar", "SharedScooter", "SharedKickScooter", "SharedBike"]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")

    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    max_walking_distance = parser.getint(vehicle_type, "WALKING_DISTANCE")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")
    initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC")

    vc = VehicleConfig(
        price_per_min,
        max_state_of_charge,
        energy_consumption,
        velocity,
        max_available_seats,
        max_walking_distance,
        daily_total_cost,
        initial_SoC,
    )
    global_config.add_vehicle_config(vehicle_type_classes[idx], vc)

# Read Mode Choice Configuration
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(',')

# User Configuration
AV_trust = parser.get("MODE_CHOICE_MODEL", "AV_trust").split(",")
AV_trust = [float(x) for x in AV_trust]
pop_prob = parser.get("MODE_CHOICE_MODEL", "population_probabilities").split(",")
pop_prob = [float(x) for x in pop_prob]

mc = ModeChoiceConfig(
    mode_choice_strategy,
    mode_choice_sub_boundary,
    mode_choice_available_modes,
    mode_choice_model_path,
)
global_config.add_mode_choice_config(mc)

# Read Shared Vehice Operator Config
recharge_threshold = parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD")
charging_station_power = parser.getfloat("SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER")
number_of_service_workers = parser.getint("SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER")
base_regions = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
base_regions = base_regions.split(',')
base_capacity = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
operations_start = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint("SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY")

svoc = SharedVehicleOperatorConfig(recharge_threshold, charging_station_power,
                                   number_of_service_workers, base_regions,
                                   base_capacity, operations_start, operations_duration,
                                   vehicle_relocation_velocity)
global_config.add_shared_vehicle_operator_config(svoc)

# Output Configuration
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

import logging

# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

logger = logging.getLogger()
logger.setLevel(log_level)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)

# Add Custom Init Filters (which work without the ENV obj)
cf_init = SimulationContextFilter(filter_name='add_env', extra=[])
logger.addFilter(cf_init)


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
        env_df_hex_9.set_index('hex_id_9', inplace=True)

    filename = env_layer_hex_8
    with open(filename) as file:
        env_df_hex_8 = gpd.read_file(file)
        env_df_hex_8.set_index('hex_id_8', inplace=True)

    filename = env_layer_hex_7
    with open(filename) as file:
        env_df_hex_7 = gpd.read_file(file)
        env_df_hex_7.set_index('hex_id_7', inplace=True)

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
di = DemandImporter(spatial_resolution=global_config.spatial_resolution,
                    temporal_resolution=global_config.temporal_resolution,
                    daily_resolution=global_config.daily_resolution)

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
        n_cars=0,
        n_scooter=0,
        n_kick_scooter=0,
        n_bikes=0,
        seed=42,
        phase=1,
        AV_trust=AV_trust,
        pop_prob=pop_prob,
        allocation=None,
        EV_penetration=1,
        AV_penetration=1,
        returnDataFrame=False,
        charging_capacity=20,
        charging_power=50,
        substitution=0.1,
        price_sensitive_pop_prob=0.0
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
    :param n_bikes:
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
    SharedCar.car_id = 0
    SharedKickScooter.shared_kick_scooter_id = 0
    SharedScooter.shared_scooter_id = 0
    User.user_id = 0
    DemandFactory.counter = 0

    GeodesicEnvironment.getInstance().reset_random_generator(seed)

    # Inject Simulation Environment to Logger (such that we can log the env time)
    cf = SimulationContextFilter(filter_name='add_env', extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. Simulation Modules.               #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Operator Modules
    search_engines = {'shared_vehicle': SharedVehicleSearchEngine(env)}
    payment_engines = search_engines
    vehicle_assignment_engines = {'shared_vehicle': SharedVehicleAllocationEngine(env)}

    # Vehicle Choice Model
    if mode_choice_strategy == "substitution":
        vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
            ['SharedScooter', 'SharedKickScooter', 'SharedCar', 'SharedBike'])
    else:
        raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

    # Population Type
    population_factory = PopulationFactory(pop_prob[0], seed)

    # Charging Infrastructure
    number_of_charging_stations = parser.getint(
        "Charging_Infrastructure", "NUMBER_OF_CHARGING_STATIONS"
    )
    charging_location_list = parser.get(
        "Charging_Infrastructure", "BASE_REGIONS"
    ).split(",")[:number_of_charging_stations]
    ### Activate it if there are specific capacity for charging stations
    charging_power_list = list(np.zeros(len(charging_location_list)) + charging_power)
    charging_capacity_list = list(
        np.zeros(len(charging_location_list)) + charging_capacity
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

    # World
    Tracking.init(env)
    world = World.init(
        env,
        search_engines,
        search_engines,
        vehicle_assignment_engines,
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
    demand_factory = DemandFactory(env, demand_profile, di, world, demand_modifier_paths, seed, mode="shared_vehicle")

    env.process(demand_factory.generate_demand())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Load Vehicle Fleet and Place on World.  #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    supply_prob = pd.read_csv(supply_file_path)

    fleet_config = generate_fleet_config(supply_prob, n_cars=n_cars, n_scooter=n_scooter, n_kick_scooter=n_kick_scooter,
                                         n_bikes=n_bikes)
    mixed_fleet = generate_mixed_fleet(env, fleet_config)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Inject Modules.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    search_engines['shared_vehicle'].register_fleet(mixed_fleet)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Operations Management Processes         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    available_vehicle_modes = ["SharedKickScooter", "SharedScooter", "SharedCar", "SharedBike"]
    available_vehicle_modes_supply = [n_kick_scooter, n_scooter, n_cars, n_bikes]
    no_service_workers = global_config.shared_vehicle_operator_config.number_of_service_worker
    base_regions = global_config.shared_vehicle_operator_config.base_regions
    base_capacity = global_config.shared_vehicle_operator_config.base_capacity

    # Initialize Rule Based Relocation Scheduler
    rs = RelocationScheduler(distance_matrix, mixed_fleet, available_vehicle_modes,
                             available_vehicle_modes_supply, no_service_workers,
                             base_regions, base_capacity)

    # Store Tasks which are processed by service workers
    task_queue = TaskQueue(env)

    # Init Operations Module
    ops = Operations(env, mixed_fleet, no_service_workers,
                     global_config.shared_vehicle_operator_config.operations_start,
                     global_config.shared_vehicle_operator_config.operations_duration, rs,
                     payment_engines["shared_vehicle"], available_vehicle_modes,
                     available_vehicle_modes_supply, global_config.shared_vehicle_operator_config.recharge_threshold,
                     task_queue)

    env.process(ops.timer())
    env.process(ops.run_operations())

    # Spawn Service Workers
    for sw in range(no_service_workers):
        env.process(ServiceWorker(env, task_queue).run())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Run Simulation.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    logging.warning(f"Starting Simulation.",
                    extra={"clazz": "main", "oid": ""})

    env.run(until=end_time)

    payment_engines["shared_vehicle"].get_transactions().to_excel('./transactions.xlsx')

    logging.warning(f"Simulation Finished.",
                    extra={"clazz": "main", "oid": ""})


# End Time
T = 1440

# Real Run
run_single_simulation(
    start_time=0,
    end_time=T,
    n_cars=800,
    n_scooter=800,
    n_kick_scooter=800,
    n_bikes=800
)
