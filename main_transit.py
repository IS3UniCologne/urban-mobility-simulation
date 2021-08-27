from simulation.agent.user import User
from simulation.helper.configuration.configuration import Configuration, UserConfig, TransitOperatorConfig
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from simulation.vehicle_choice_model.public_transit_vehicle_choice_behavior import PublicTransitVehicleChoiceBehavior
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.infrastructure.helper.timetable import Timetable
from simulation.infrastructure.helper.distance_matrix_importer import DistanceMatrixImporter
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.world.world import World

from pathlib import Path
import pandas as pd
import geopandas as gpd
import simpy

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
spatial_res  = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Input Files (Infrastructure)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")
# transit_shapes_path = parser.get("INFRASTRUCTURE", "path_transit_shapes")

# Operator Config
transit_planning_lookahead = parser.get("OPERATOR", "TRANSIT_LOOKAHEAD")

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res)

# User configuration
max_waiting_time = parser.get("USER", "TRANSIT_MAX_WAIT")
spatial_strategy = parser.get("USER", "SPATIAL_STRATEGY")

user_config = UserConfig(spatial_strategy, max_waiting_time)
transit_operator_config = TransitOperatorConfig(transit_planning_lookahead)

global_config.add_user_config(user_config)
global_config.add_transit_operator_config(transit_operator_config)

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
logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

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
        env_df_hex_9 = gpd.read_file(file, driver= "GeoJSON")
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
dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure")
distance_matrix = dmi.load_distance_matrix()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timetable = Timetable(transit_timetable_path)
timetable.import_timetable()

def run_single_simulation(start_time = 0, end_time = 60, seed = 4711):

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Setup Simulation Environment.           #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Simulation Environment
    env = simpy.Environment(initial_time=start_time)

    # before a new simulation run, reset everything
    PublicTransitVehicle.public_transit_vehicle_id = 0
    Bus.bus_id = 0
    User.user_id = 0
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
    operator = PublicTransitOperator(env, timetable)
    search_engine = operator
    payment_engine = operator
    vehicle_assignment_engine = operator

    # Vehicle Choice Model
    vehicle_choice_model = PublicTransitVehicleChoiceBehavior(['Bus'])

    # World
    world = World(env, search_engine, search_engine, vehicle_assignment_engine, vehicle_choice_model)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Spawn Demand Processes.                 #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    demand_factory = DemandFactory(env, demand_profile, di, world, seed)

    env.process(demand_factory.generate_demand())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Run Simulation.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    env.run(until = end_time)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Benchmarks.                             #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    print("Total Revenue: " + str(payment_engine.total_revenue))
    print("Total Fulfilled Trips: " + str(payment_engine.total_fulfilled_trips))
    print("Total Missed Trips: " + str(payment_engine.total_missed_trips))


if __name__ == '__main__':
    run_single_simulation(end_time=10*60)
