##### This is a template for a sharedvehicle fleet consisting of shared cars, schared scooters and shared kickscooters. Shared bikes are not yet added ########

##Imports
# Standard library imports
import logging
import os
import sys
from configparser import ConfigParser
from pathlib import Path

import pandas as pd

# Third-party library imports
import simpy

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    Configuration,
    ModeChoiceConfig,
    SharedVehicleConfig,
    SharedVehicleOperatorConfig,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)

# Import operator related modules
from simulation.operator.fleet_factory import (
    generate_fleet_config,
    generate_mixed_fleet,
)
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine

# Import vehicle types and vehicle choice options
from simulation.vehicle.shared_bike import SharedBike
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle_choice_model.distance_based_shared_vehicle_choice_behavior import (
    DistanceBasedSharedVehicleVehicleChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking

# Custom module imports
from utils import load_environment

pd.set_option("display.max_columns", None)

# Change working directory to path of main.py
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Basic Configuration                     #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Experiment Management
start_time = parser.getint("EXPERIMENT_MANAGEMENT", "START_TIME")
end_time = parser.getint("EXPERIMENT_MANAGEMENT", "END_TIME")
seed = parser.getint("EXPERIMENT_MANAGEMENT", "SEED")

# World / Resolution Config
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
city = parser.get("WORLD", "city")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city=city)

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")
# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# User and Mode Choice Configuration
# TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/49
# Check the configuration file before running this, this mode needs only one probability which is the probability of a user being price sensitive or not. Other modes might require multiple inputs.
pop_prob_sharedvehicle = parser.get(
    "SHARED_VEHICLE_OPERATOR", "population_probabilities"
).split(",")
pop_prob_sharedvehicle = [float(x) for x in pop_prob_sharedvehicle]

mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")

mc = ModeChoiceConfig(
    mode_choice_strategy, mode_choice_sub_boundary, mode_choice_model_path
)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Shared Vehicle Fleet Configuration      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Read Shared Vehicle Config and add to Global Config File
# TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/46
# TODO: SharedScooters and SharedKickScooters do not have an initial state of charge. They start with the max state of charge.
for idx, vehicle_type in enumerate(
    ["SHARED_BIKE", "SHARED_CAR", "SHARED_SCOOTER", "SHARED_KICK_SCOOTER"]
):  # TODO: Can't we get a list from the Config dynamically?
    vehicle_type_classes = [
        "SharedBike",
        "SharedCar",
        "SharedScooter",
        "SharedKickScooter",
    ]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    max_walking_distance = parser.getint(vehicle_type, "WALKING_DISTANCE")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")

    if vehicle_type == "SHARED_CAR":
        initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC")
    else:
        initial_SoC = None

    vc = SharedVehicleConfig(
        price_per_min,
        max_state_of_charge,
        energy_consumption,
        velocity,
        max_available_seats,
        max_walking_distance,
        daily_total_cost,
        initial_SoC,
    )
    global_config.add_shared_vehicle_config(vehicle_type_classes[idx], vc)

# Check the configuration file before running this, different modes might require multiple inputs
# Vehicles whose state of charge is below the threshold value are to be charged
recharge_threshold = (
    parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD") / 100
)
charging_station_power = parser.getfloat(
    "SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER"
)
number_of_service_workers = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER"
)
number_of_base_regions = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_BASE_REGIONS"
)
# Hexagons as base regions for service workers to operate
base_regions = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
base_regions = base_regions.split(",")[:number_of_base_regions]

base_capacity = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
operations_start = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY"
)

# Get number of each vehicle type to be spawned from configuration
n_cars = parser.getint("EXPERIMENT_MANAGEMENT", "N_CARS")
n_kick_scooters = parser.getint("EXPERIMENT_MANAGEMENT", "N_KICKSCOOTER")
n_bikes = parser.getint("EXPERIMENT_MANAGEMENT", "N_BIKES")
n_scooters = parser.getint("EXPERIMENT_MANAGEMENT", "N_SCOOTER")

available_modes = parser.get(
    "SHARED_VEHICLE_OPERATOR", "available_vehicle_modes_shared_vehicle"
)
available_modes = available_modes.split(",")
available_modes_supply = [n_cars, n_scooters, n_kick_scooters, n_bikes]

svoc = SharedVehicleOperatorConfig(
    recharge_threshold,
    charging_station_power,
    number_of_service_workers,
    base_regions,
    base_capacity,
    operations_start,
    operations_duration,
    vehicle_relocation_velocity,
    available_modes,
    available_modes_supply,
    n_cars,
    n_scooters,
    n_kick_scooters,
    n_bikes,
)

# Vehicle Choice Model
if mode_choice_strategy == "substitution":
    vehicle_choice_model = DistanceBasedSharedVehicleVehicleChoiceBehavior(
        mode_choice_model_path, mode_choice_sub_boundary, available_modes
    )
else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

# Register all configurations
global_config.add_mode_choice_config(mc)
global_config.add_shared_vehicle_operator_config(svoc)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=0)

# Population Type
population_factory = PopulationFactory(pop_prob_sharedvehicle, seed)

# Load Spatial Environment
load_environment(  # city=city
)

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
dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure", city=city)
distance_matrix = dmi.load_distance_matrix()

GeodesicEnvironment.getInstance().reset_random_generator(4711)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Reset counters and random number        #
# generators before each run              #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

SharedBike.shared_bike_id = 0
SharedCar.car_id = 0
SharedKickScooter.shared_kick_scooter_id = 0
SharedScooter.shared_scooter_id = 0
User.user_id = 0
DemandFactory.counter = 0

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Output Configuration                    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

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
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

tracking = Tracking.init(env)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
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

# Inject Simulation Environment to Logger (such that we can log the env time)
# Add Custom Init Filters (which work without the ENV obj)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
edf = ExtraDefaultFilter(filter_name="add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules.               #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Search Engine finds transportation alternatives for users and manages payment processes
search_engine = SharedVehicleSearchEngine(env)

# Vehicle Assignment Engine assigns users to vehicles and notifies them about the pickup position
vehicle_assignment_engine = SharedVehicleAllocationEngine(env)

# Configure and generate / spawn shared fleet vehicles
shared_vehicle_fleet_config = generate_fleet_config(
    supply_prob,
    n_cars=global_config.shared_vehicle_operator_config.n_cars,
    n_scooter=global_config._shared_vehicle_operator_config.n_scooters,
    n_kick_scooter=global_config.shared_vehicle_operator_config.n_kickscooters,
    n_bikes=global_config.shared_vehicle_operator_config.n_bikes,
)
mixed_fleet = generate_mixed_fleet(env, shared_vehicle_fleet_config)

# Add the fleet to the search engine
search_engine.register_fleet(mixed_fleet)

# Init Operations Module

operations = IntegratedSharedMobilityOperations(
    env=env,
    time_between_operations=global_config.shared_vehicle_operator_config.operations_start,
    operation_duration=global_config.shared_vehicle_operator_config.operations_duration,
    distance_matrix=distance_matrix,
    ordered_available_vehicle_modes=available_modes,
    ordered_max_vehicle_supply=available_modes_supply,
    state_of_charge_threshold=global_config.shared_vehicle_operator_config.recharge_threshold,
    base_regions=global_config.shared_vehicle_operator_config.base_regions,
    base_capacity=global_config.shared_vehicle_operator_config.base_capacity,
)

# Init operator
operator = SharedMobilityOperator(
    env=env,
    fleet=mixed_fleet,
    charging_infrastructure=None,
    operations=operations,
    search_engine=search_engine,
    allocation_engine=vehicle_assignment_engine,
    number_service_workers=number_of_service_workers,
)

# Initialize World
world = World.init(
    env=env,
    search_engine=search_engine,
    payment_engine=operator,
    vehicle_assignment_engine=vehicle_assignment_engine,
    vehicle_choice_behavior=vehicle_choice_model,
    population_factory=population_factory,
    charging_infrastructure=None,
    reset=True,
)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Spawn Demand Processes.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: we need to have a look at https://github.com/IS3UniCologne/urban-mobility-simulation/issues/32
demand_factory = DemandFactory(
    env, demand_profile, di, world, [], seed, mode="shared_vehicle"
)
env.process(demand_factory.generate_demand())

# Start the operations of the shared operator
env.process(operations.execute())

logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

# Run the simulation until end time
env.run(until=50)

logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})
