from pathlib import Path
import pandas as pd

from simulation.helper.configuration.configuration import Configuration
from simulation.operator.fleet_factory import generate_fleet_config, generate_mixed_fleet
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.world import World
pd.set_option('display.max_columns', None)
import simpy
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.operator.shared_vehicle_allocation_engine import SharedVehicleAllocationEngine
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
import geopandas as gpd

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

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res)

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

# Add Custom Filters
# cf = SimulationContextFilter(filter_name='add_env', extra=env)
# edf = ExtraDefaultFilter(filter_name = "add_default_value")
# logger.addFilter(cf)
# logger.addFilter(edf)

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


def run_single_simulation(start_time = 0, end_time = 20, n_cars = 100, n_scooter = 100, n_kick_scooter = 100):
  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Setup Simulation Environment.           #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #

  # Simulation Environment
  env = simpy.Environment(initial_time=start_time)

  from simulation.vehicle.shared_car import SharedCar
  from simulation.vehicle.shared_kick_scooter import SharedKickScooter
  from simulation.vehicle.shared_scooter import SharedScooter
  from simulation.agent.user import User

  # Before each simulation run, reset counter and random number generators
  SharedCar.car_id = 0
  SharedKickScooter.shared_kick_scooter_id = 0
  SharedScooter.shared_scooter_id = 0
  User.user_id = 0
  DemandFactory.counter = 0

  GeodesicEnvironment.getInstance().reset_random_generator()

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
  search_engine = SharedVehicleSearchEngine(env)
  payment_engine = search_engine
  vehicle_assignment_engine = SharedVehicleAllocationEngine(env)

  # World
  world = World(env, search_engine, search_engine, vehicle_assignment_engine)

  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Spawn Demand Processes.                 #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #
  demand_factory = DemandFactory(env, demand_profile, di, world)

  env.process(demand_factory.generate_demand())

  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Load Vehicle Fleet and Place on World.  #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #
  supply_prob = pd.read_csv(supply_file_path)

  fleet_config = generate_fleet_config(supply_prob, n_cars = n_cars, n_scooter = n_scooter, n_kick_scooter= n_kick_scooter, n_bikes=0)
  mixed_fleet = generate_mixed_fleet(env, fleet_config)

  # TODO: [Testing]
  # Artifically add vehicle (see world add new user)
  # Access to underlying geodesic environment
  # geo_env = GeodesicEnvironment.getInstance()
  # from simulation.environment.geodesic_position import GeodesicPosition
  # from simulation.vehicle.shared_car import SharedCar
  # rdm_lat, rdm_lng = geo_env.get_random_position('871f1d498ffffff')
  #
  # pos = GeodesicPosition(rdm_lat, rdm_lng)
  # car = SharedCar(env, pos)
  # car_2 = SharedCar(env, pos)
  # mixed_fleet.add_shared_vehicle(car)
  # mixed_fleet.add_shared_vehicle(car_2)

  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Inject Modules.                         #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #
  search_engine.register_fleet(mixed_fleet)

  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Run Simulation.                         #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #
  env.run(until = end_time)


  print("Total Revenue: " + str(payment_engine.total_revenue))
  print("Total Fulfilled Trips: " + str(payment_engine.total_fulfilled_trips))
  print("Total Missed Trips: " + str(payment_engine.total_missed_trips))

  print(DemandFactory.counter)

# TODO: Pass seed to sub modules otherwise they are always set to 42
run_single_simulation(end_time = 1440, n_cars = 1000, n_scooter = 0, n_kick_scooter = 0)
# run_single_simulation(end_time = 60, n_cars = 200, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 300, n_scooter = 0, n_kick_scooter = 0)
# run_single_simulation(end_time = 60, n_cars = 400, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 500, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 600, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 700, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 800, n_scooter = 0, n_kick_scooter = 0)

# run_single_simulation(end_time = 60, n_cars = 200, n_scooter = 0, n_kick_scooter = 0)
