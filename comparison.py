# This file compares (current expertiment_template with) main.py and main_dynamicrouting.py (?)

### Imports 
from pathlib import Path
import sys
from configparser import ConfigParser
import os

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
from simulation.helper.configuration.configuration import Configuration
# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

# World / Resolution Config
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
#Dynamic.py has also "city"

### Input Files
# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Supply)
import pandas as pd
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")
# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)

# Input Files (Public Transit Operator / Timetable)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

### Vehicle Configuration
# Shared Vehicle Config
from simulation.helper.configuration.configuration import VehicleConfig
price_per_min = parser.getfloat("SHARED_CAR", "PRICE_PER_MIN")
max_state_of_charge = parser.getfloat("SHARED_CAR", "MAX_STATE_OF_CHARGE")
energy_consumption = parser.getfloat("SHARED_CAR", "ENERGY_CONSUMPTION")
velocity = parser.getfloat("SHARED_CAR", "VELOCITY")
max_available_seats = parser.getint("SHARED_CAR", "MAX_AVAILABLE_SEATS")
max_walking_distance = parser.getint("SHARED_CAR", "WALKING_DISTANCE")
daily_total_cost = parser.getfloat("SHARED_CAR", "DAILY_TOTAL_COST")
initial_SoC = parser.getfloat("SHARED_CAR", "INITIAL_SOC")

vc = VehicleConfig(price_per_min, max_state_of_charge, energy_consumption, velocity, max_available_seats,
                    max_walking_distance, daily_total_cost, initial_SoC)

## Busses and PublicTransitOperator

# Bus Vehicle Config
from simulation.helper.configuration.configuration import BusConfig
bus_config = BusConfig(
    max_available_seats=parser.getint("BUS", "SEATS"),
    velocity=parser.getfloat("BUS", "VELOCITY")
)

# Public Transit Operator Config
from simulation.helper.configuration.configuration import TransitOperatorConfig
transit_operator_config = TransitOperatorConfig(
    planning_lookahead=parser.getint("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD"),
    max_busses=parser.getint("TRANSIT_OPERATOR", "MAX_BUSSES")
)

# User and Moide Choice Configuration
from simulation.helper.configuration.configuration import ModeChoiceConfig
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(',')
pop_prob = parser.get("MODE_CHOICE_MODEL", "population_probabilities").split(',')
pop_prob = [float(x) for x in pop_prob]

mc = ModeChoiceConfig(mode_choice_strategy, mode_choice_sub_boundary, mode_choice_available_modes,
                      mode_choice_model_path)

# Shared Vehicle Configuration
from simulation.helper.configuration.configuration import SharedVehicleOperatorConfig

# Read Shared Vehicle Operator Config
# recharge_threshold = parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD")
recharge_threshold = parser.get("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD").split(',')
recharge_threshold = [float(x) / 100 for x in recharge_threshold]
global_config.add_recharging_threshold(recharge_threshold)

charging_station_power = parser.getfloat("SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER")
number_of_service_workers = parser.getint("SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER")
number_of_base_regions = parser.getint("SHARED_VEHICLE_OPERATOR", "NUMBER_OF_BASE_REGIONS")
base_regions = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
base_regions = base_regions.split(',')[:number_of_base_regions]
base_capacity = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
operations_start = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint("SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY")

svoc = SharedVehicleOperatorConfig(recharge_threshold, charging_station_power,
                                   number_of_service_workers, base_regions,
                                   base_capacity, operations_start, operations_duration,
                                   vehicle_relocation_velocity)

# Register every config in the global configuration
# - Shared Vehicles
global_config.add_vehicle_config("Shared_Car", vc)
# - Bus + PublicTransitOperator
global_config.add_bus_config(bus_config)
global_config.add_transit_operator_config(transit_operator_config)
# - User / Mode Choice
global_config.add_mode_choice_config(mc)
# - Shared Vehicle Operator
global_config.add_shared_vehicle_operator_config(svoc)

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

## Spatial Environment
import geopandas as gpd
from utils import load_environment
# Load Spatial Environment
load_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Demand Data (once).                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
from simulation.world.demand.demand_importer import DemandImporter
p = Path(demand_file_path)
di = DemandImporter(spatial_resolution=global_config.spatial_resolution,
                    temporal_resolution=global_config.temporal_resolution,
                    daily_resolution=global_config.daily_resolution,
                    city=global_config.city)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.infrastructure.helper.distance_matrix_importer import DistanceMatrixImporter

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(f"hex_{spatial_res}").index.tolist()
dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure", city)
distance_matrix = dmi.load_distance_matrix()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
import simpy
env = simpy.Environment(initial_time=0)
############################################################################
#                                                                          #
#  Before each simulation run, reset counter and random number generators  #
#                                                                          #
############################################################################
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle.public_transit_bus import Bus
from simulation.agent.user import User  # must come before DemandFactory, otherwise circular imports
from simulation.world.demand.demand_factory import DemandFactory

SharedCar.car_id = 0
SharedKickScooter.shared_kick_scooter_id = 0
SharedScooter.shared_scooter_id = 0
Bus.bus_id = 0
User.user_id = 0

DemandFactory.counter = 0

GeodesicEnvironment.getInstance().reset_random_generator(4711)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Log Level
log_level = parser.get("SETTINGS", "log_level")

import logging

# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

logger = logging.getLogger()
logger.setLevel(log_level)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s')
file_handler = logging.FileHandler('report.log')
file_handler.setFormatter(formatter)
file_handler.setLevel(log_level)

# Add Custom Init Filters (which work without the ENV obj)
cf_init = SimulationContextFilter(filter_name='add_env', extra=[])
logger.addFilter(cf_init)

# Inject Simulation Environment to Logger (such that we can log the env time)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
cf = SimulationContextFilter(filter_name='add_env', extra=env)
edf = ExtraDefaultFilter(filter_name="add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

from tracking.tracking import Tracking
tracking = Tracking.init(env)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# PublicTransitOperator // starts its own processes & also includes vehicle spawn
from simulation.operator.public_transit_operator import PublicTransitOperator
pt_operator = PublicTransitOperator(env, timetable)

# Fleet of vehicles: Configure + Generate
from simulation.operator.fleet_factory import generate_mixed_fleet, generate_fleet_config
# Get number of each vehicle type to be spawned from configuration
n_cars = parser.getint("EXPERIMENT_MANAGEMENT", "N_CARS")
n_kick_scooter = parser.getint("EXPERIMENT_MANAGEMENT", "N_KICKSCOOTER")
n_bikes = parser.getint("EXPERIMENT_MANAGEMENT", "N_BIKES")
n_scooter = parser.getint("EXPERIMENT_MANAGEMENT", "N_SCOOTER")
# Configure and generate / spawn vehicles
fleet_config = generate_fleet_config(supply_prob, n_cars = n_cars, n_scooter = n_scooter, n_kick_scooter= n_kick_scooter, n_bikes=n_bikes)
mixed_fleet = generate_mixed_fleet(env, fleet_config)