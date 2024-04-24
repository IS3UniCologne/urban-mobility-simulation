import logging
import os
import random
import sys
from configparser import ConfigParser
from pathlib import Path

import geopandas as gpd
import pandas as pd
import simpy

from simulation.agent.user import (
    User,  # must come before DemandFactory, otherwise circular imports
)
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import (
    BusConfig,
    Configuration,
    ModeChoiceConfig,
    TransitOperatorConfig,
    VehicleConfig,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.infrastructure.helper.timetable import Timetable
from simulation.operator.fleet_factory import (
    generate_fleet_config,
    generate_mixed_fleet,
)
from simulation.operator.operations_management.operations import Operations
from simulation.operator.operations_management.relocation_scheduler import (
    RelocationScheduler,
)
from simulation.operator.operations_management.service_worker import ServiceWorker
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking

pd.set_option("display.max_columns", None)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load and register Configuration         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Change working directory to path of main.py
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

##################################
# Experiment Management
##################################
start_time = parser.getint("EXPERIMENT_MANAGEMENT", "START_TIME")
end_time = parser.getint("EXPERIMENT_MANAGEMENT", "END_TIME")
seed = parser.getint("EXPERIMENT_MANAGEMENT", "SEED")

n_cars = parser.getint("EXPERIMENT_MANAGEMENT", "N_CARS")
n_kick_scooter = parser.getint("EXPERIMENT_MANAGEMENT", "N_KICKSCOOTER")
n_bikes = parser.getint("EXPERIMENT_MANAGEMENT", "N_BIKES")
n_scooter = parser.getint("EXPERIMENT_MANAGEMENT", "N_SCOOTER")


# World Config
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
city = parser.get("WORLD", "city")

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
# optional: demand modifiers, geojson with property demandMultiplier
# demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")
supply_prob = pd.read_csv(supply_file_path)

# Input Files (Infrastructure & Supply)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

##################################
# Exemplary vehicle configurations
##################################

# Shared Vehicle Config
price_per_min = parser.getfloat("SHARED_CAR", "PRICE_PER_MIN")
max_state_of_charge = parser.getfloat("SHARED_CAR", "MAX_STATE_OF_CHARGE")
energy_consumption = parser.getfloat("SHARED_CAR", "ENERGY_CONSUMPTION")
velocity = parser.getfloat("SHARED_CAR", "VELOCITY")
max_available_seats = parser.getint("SHARED_CAR", "MAX_AVAILABLE_SEATS")
max_walking_distance = parser.getint("SHARED_CAR", "WALKING_DISTANCE")
daily_total_cost = parser.getfloat("SHARED_CAR", "DAILY_TOTAL_COST")
initial_SoC = parser.getfloat("SHARED_CAR", "INITIAL_SOC")

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


# Bus Vehicle Config
bus_config = BusConfig(
    max_available_seats=parser.getint("BUS", "SEATS"),
    velocity=parser.getfloat("BUS", "VELOCITY"),
)

#############################
# User (and Operator) Config
#############################

# User Configuration
price_sensitive_pop_prob = parser.get("USER", "PRICE_SENSITIVE")


mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(",")
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

# Public Transit Operator Config
transit_operator_config = TransitOperatorConfig(
    planning_lookahead=parser.getint("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD"),
    max_busses=parser.getint("TRANSIT_OPERATOR", "MAX_BUSSES"),
)

# we need to register every config in the global configuration
global_config.add_vehicle_config("Shared_Car", vc)
global_config.add_bus_config(bus_config)

global_config.add_mode_choice_config(mc)
global_config.add_transit_operator_config(transit_operator_config)

######################
# Output Configuration
######################

store_results = parser.getboolean("OUTPUT", "persist_results")
store_results = parser.getboolean("OUTPUT", "persist_results")
output_folder = parser.get("OUTPUT", "output_folder")
transaction_file = parser.get("OUTPUT", "transaction_file")
fleet_state_file = parser.get("OUTPUT", "fleet_state_file")

global_config.set_store_results(store_results)
global_config.set_output_path(output_folder)
global_config.set_transaction_file(transaction_file)
global_config.set_fleet_state_file(fleet_state_file)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Configure Logging.                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Log Level
log_level = parser.get("SETTINGS", "log_level")


# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)

logger = logging.getLogger()
logger.setLevel(log_level)

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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Underlying Spatial Environment.    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


def load_environment():
    # Read Environment Files
    filename = bounding_box_path
    with open(filename) as file:
        env_df = gpd.read_file(file, driver="GeoJSON")

    filename = env_layer_hex_9
    with open(filename) as file:
        env_df_hex_9 = gpd.read_file(file, driver="GeoJSON")
        env_df_hex_9.set_index("hex_id_9", inplace=True)

    filename = env_layer_hex_8
    with open(filename) as file:
        env_df_hex_8 = gpd.read_file(file, driver="GeoJSON")
        env_df_hex_8.set_index("hex_id_8", inplace=True)

    filename = env_layer_hex_7
    with open(filename) as file:
        env_df_hex_7 = gpd.read_file(file, driver="GeoJSON")
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
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timetable = Timetable(transit_timetable_path)
timetable.import_timetable()

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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Setup Simulation Environment.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Simulation Environment
env = simpy.Environment(initial_time=0)

# Before each simulation run, reset counter and random number generators
SharedCar.car_id = 0
SharedKickScooter.shared_kick_scooter_id = 0
SharedScooter.shared_scooter_id = 0
Bus.bus_id = 0
User.user_id = 0
DemandFactory.counter = 0

GeodesicEnvironment.getInstance().reset_random_generator(4711)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
edf = ExtraDefaultFilter(filter_name="add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
tracking = Tracking.init(env)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules.               #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Operator Modules

# PublicTransitOperator starts its own processes & also includes vehicle spawn
pt_operator = PublicTransitOperator(env, timetable)


# Shared_Fleet
fleet_config = generate_fleet_config(
    supply_prob,
    n_cars=n_cars,
    n_scooter=n_scooter,
    n_kick_scooter=n_kick_scooter,
    n_bikes=n_bikes,
)
mixed_fleet = generate_mixed_fleet(env, fleet_config)

# Shared Vehicles Operator is more atomic and needs some functionalities initialized beforehand
available_vehicle_modes = [
    "SharedKickScooter",
    "SharedScooter",
    "SharedCar",
    "SharedBike",
]
available_vehicle_modes_supply = [n_kick_scooter, n_scooter, n_cars, n_bikes]
no_service_workers = (
    global_config.shared_vehicle_operator_config.number_of_service_worker
)
base_regions = global_config.shared_vehicle_operator_config.base_regions
base_capacity = global_config.shared_vehicle_operator_config.base_capacity

search_engine = {
    "shared_vehicle": SharedVehicleSearchEngine(env),
    "public_transport": pt_operator,
}
payment_engine = search_engine
vehicle_assignment_engine = {
    "shared_vehicle": SharedVehicleAllocationEngine(env),
    "public_transport": pt_operator,
}

# Initialize Rule Based Relocation Scheduler
relocation_scheduler = RelocationScheduler(
    distance_matrix,
    mixed_fleet,
    available_vehicle_modes,
    available_vehicle_modes_supply,
    no_service_workers,
    base_regions,
    base_capacity,
)

# Store Tasks which are processed by service workers
task_queue = TaskQueue(env)

# Init Operations Module
shared_operator = Operations(
    env,
    mixed_fleet,
    no_service_workers,
    global_config.shared_vehicle_operator_config.operations_start,
    global_config.shared_vehicle_operator_config.operations_duration,
    relocation_scheduler,
    payment_engine,
    available_vehicle_modes,
    available_vehicle_modes_supply,
    global_config.shared_vehicle_operator_config.recharge_threshold,
    task_queue,
)

env.process(shared_operator.timer())
env.process(shared_operator.run_operations())

# Spawn Service Workers
for sw in range(no_service_workers):
    env.process(ServiceWorker(env, task_queue).run())

# Vehicle Choice Model
vehicle_choice_model = (
    None  # TODO: implement choice models that can use different modes
)

# Population Type
population_factory = PopulationFactory(price_sensitive_pop_prob, seed)

# World
world = World.init(
    env,
    search_engine,
    search_engine,
    vehicle_assignment_engine,
    vehicle_choice_model,
    population_factory,
    charging_infrastructure=None,
    reset=True,
)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Spawn Demand Processes.                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
# TODO: we need to have a look at https://github.com/IS3UniCologne/urban-mobility-simulation/issues/32
# for now, we spawn by chance
silly_choice = "public_transport" if random.random() < 0.5 else "shared_vehicle"

demand_factory = DemandFactory(
    env, demand_profile, di, world, [], seed, mode=silly_choice
)
env.process(demand_factory.generate_demand())
