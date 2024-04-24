# This file compares (current expertiment_template with) main.py and main_dynamicrouting.py (?)

### Imports
import os
import sys
from configparser import ConfigParser
from pathlib import Path

import simpy

# Before each simulation run, reset counter and random number generators
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# must come before DemandFactory, otherwise circular imports
from simulation.helper.configuration.configuration import (
    BusConfig,
    Configuration,
    ModeChoiceConfig,
    SharedVehicleOperatorConfig,
    TransitOperatorConfig,
    VehicleConfig,
)
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.infrastructure.helper.timetable import Timetable
from simulation.operator.operations_management.task_queue import TaskQueue

# PublicTransitOperator // starts its own processes & also includes vehicle spawn
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter

# must come before DemandFactory, otherwise circular imports
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from utils import load_environment

# Change working directory to path of main.py
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

### Experiment Management
start_time = parser.getint("EXPERIMENT_MANAGEMENT", "START_TIME")
end_time = parser.getint("EXPERIMENT_MANAGEMENT", "END_TIME")
seed = parser.getint("EXPERIMENT_MANAGEMENT", "SEED")

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Configuration                           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


# World / Resolution Config
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
city = parser.get("WORLD", "city")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

### Input Files
# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")
# Get the supply probability from supply file
# supply_prob = pd.read_csv(supply_file_path)

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# User and Moide Choice Configuration

mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(",")
pop_prob = parser.get("MODE_CHOICE_MODEL", "population_probabilities").split(",")
pop_prob = [float(x) for x in pop_prob]

mc = ModeChoiceConfig(
    mode_choice_strategy,
    mode_choice_sub_boundary,
    mode_choice_available_modes,
    mode_choice_model_path,
)

# Register User / Mode Choice
global_config.add_mode_choice_config(mc)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=0)

# Population Type

population_factory = PopulationFactory(pop_prob, seed)

## Spatial Environment

# Load Spatial Environment
load_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Operations Management Processes         #
#                                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Store Tasks which are processed by service workers

task_queue_ridehailing = TaskQueue(env)


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

# demand_profile = di.extract_spatio_temporal_demand_estimates(p)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(f"hex_{spatial_res}").index.tolist()
dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure", city)
distance_matrix = dmi.load_distance_matrix()

GeodesicEnvironment.getInstance().reset_random_generator(4711)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# If you want busses, use this block      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


Bus.bus_id = 0
User.user_id = 0
DemandFactory.counter = 0

# Input Files (Public Transit Operator / Timetable)  ??? Main.py does not have this
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")

## Busses and PublicTransitOperator

# Bus Vehicle Config

bus_config = BusConfig(
    max_available_seats=parser.getint("BUS", "SEATS"),
    velocity=parser.getfloat("BUS", "VELOCITY"),
)

# Public Transit Operator Config

transit_operator_config = TransitOperatorConfig(
    planning_lookahead=parser.getint("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD"),
    max_busses=parser.getint("TRANSIT_OPERATOR", "MAX_BUSSES"),
)

# Register the config
global_config.add_bus_config(bus_config)
global_config.add_transit_operator_config(transit_operator_config)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timetable = Timetable(transit_timetable_path)
# timetable.import_timetable()
pt_operator = PublicTransitOperator(env, timetable)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# If you want shared vehicle fleet,       #
#  use this block                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Before each simulation run, reset counter and random number generators

SharedCar.car_id = 0
SharedKickScooter.shared_kick_scooter_id = 0
SharedScooter.shared_scooter_id = 0
User.user_id = 0
DemandFactory.counter = 0

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


# Read Shared Vehicle Operator Config
# recharge_threshold = parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD")
recharge_threshold = parser.get("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD").split(
    ","
)
recharge_threshold = [float(x) / 100 for x in recharge_threshold]
global_config.add_recharging_threshold(recharge_threshold)

charging_station_power = parser.getfloat(
    "SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER"
)
number_of_service_workers = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER"
)
number_of_base_regions = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_BASE_REGIONS"
)
base_regions = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
base_regions = base_regions.split(",")[:number_of_base_regions]
base_capacity = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
operations_start = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY"
)

svoc = SharedVehicleOperatorConfig(
    recharge_threshold,
    charging_station_power,
    number_of_service_workers,
    base_regions,
    base_capacity,
    operations_start,
    operations_duration,
    vehicle_relocation_velocity,
)

# Register the configs
global_config.add_vehicle_config("Shared_Car", vc)
global_config.add_shared_vehicle_operator_config(svoc)

print(operations_start)
print(global_config.shared_vehicle_operator_config.operations_start)
