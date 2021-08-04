from pathlib import Path
import pandas as pd

from simulation.helper.configuration.configuration import Configuration, VehicleConfig, ModeChoiceConfig
from simulation.infrastructure.helper.distance_matrix_importer import DistanceMatrixImporter
from simulation.operator.fleet_factory import generate_fleet_config, generate_mixed_fleet
from simulation.operator.operations_management.operations import Operations
from simulation.operator.operations_management.relocation_scheduler import RelocationScheduler
from simulation.operator.operations_management.service_worker import ServiceWorker
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.vehicle_choice_model.distance_based_shared_vehicle_choice_behavior import \
  DistanceBasedSharedVehicleVehicleChoiceBehavior
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

# Read Shared Vehicle Config and add to Global Config File
for idx, vehicle_type in enumerate(["SHARED_CAR", "SHARED_SCOOTER", "SHARED_KICK_SCOOTER"]):
  vehicle_type_classes = ["SharedCar", "SharedScooter", "SharedKickScooter"]
  price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
  max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
  energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
  velocity = parser.getfloat(vehicle_type, "VELOCITY")
  max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")

  vc = VehicleConfig(price_per_min, max_state_of_charge, energy_consumption, velocity, max_available_seats)
  global_config.add_vehicle_config(vehicle_type_classes[idx], vc)

# Read Mode Choice Configuration
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(',')

# Output
store_results = parser.getboolean("OUTPUT", "persist_results")
output_folder = parser.get("OUTPUT", "output_folder")
transaction_file   = parser.get("OUTPUT", "transaction_file")
fleet_state_file   = parser.get("OUTPUT", "fleet_state_file")

global_config.set_store_results(store_results)
global_config.set_output_path(output_folder)
global_config.set_transaction_file(transaction_file)
global_config.set_fleet_state_file(fleet_state_file)

mc = ModeChoiceConfig(mode_choice_strategy, mode_choice_sub_boundary, mode_choice_available_modes, mode_choice_model_path)
global_config.add_mode_choice_config(mc)


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

def run_single_simulation(start_time = 0, end_time = 20, n_cars = 0, n_scooter = 0, n_kick_scooter = 0, seed = 42, substitution = 0.1):
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
  search_engine = SharedVehicleSearchEngine(env)
  payment_engine = search_engine
  vehicle_assignment_engine = SharedVehicleAllocationEngine(env)

  # Vehicle Choice Model
  if mode_choice_strategy == "substitution":
    vehicle_choice_model = DistanceBasedSharedVehicleVehicleChoiceBehavior(mode_choice_model_path,
                                                                           substitution,
                                                                           mode_choice_available_modes)
  else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

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
  # Load Vehicle Fleet and Place on World.  #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #
  supply_prob = pd.read_csv(supply_file_path)

  fleet_config = generate_fleet_config(supply_prob, n_cars = n_cars, n_scooter = n_scooter, n_kick_scooter= n_kick_scooter, n_bikes=0)
  mixed_fleet = generate_mixed_fleet(env, fleet_config)

  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Inject Modules.                         #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #
  search_engine.register_fleet(mixed_fleet)

  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Operations Management Processes         #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #


  available_vehicle_modes = ["SharedKickScooter", "SharedScooter", "SharedCar"]
  available_vehicle_modes_supply = [n_kick_scooter, n_scooter, n_cars]
  no_service_workers = 100
  base_region = ['871f1d488ffffff']
  base_capacity = 10000

  # Initialize Rule Based Relocation Scheduler
  rs = RelocationScheduler(distance_matrix, mixed_fleet, available_vehicle_modes,
                           available_vehicle_modes_supply, no_service_workers,
                           base_region, base_capacity)

  # Store Tasks which are processed by service workers
  task_queue = TaskQueue(env)

  # Init Operations Module
  ops = Operations(env, mixed_fleet, no_service_workers, 1440, rs,
                   payment_engine, available_vehicle_modes,
                   available_vehicle_modes_supply, 0.1, task_queue)

  env.process(ops.run_operations())

  # Spawn Service Workers
  for sw in range(no_service_workers):
    env.process(ServiceWorker(env, task_queue).run())

  # Create Second Service Workers
  # env.process(ServiceWorker(env, ops).run())


  # # # # # # # # # # # # # # # # # # # # # #
  #                                         #
  # Run Simulation.                         #
  #                                         #
  # # # # # # # # # # # # # # # # # # # # # #
  env.run(until = end_time)


  print("Total Revenue: " + str(payment_engine.total_revenue))
  print("Total Fulfilled Trips: " + str(payment_engine.total_fulfilled_trips))
  print("Total Missed Trips: " + str(payment_engine.total_missed_trips))

  print("Number of Vehicles to be charged: " + str(mixed_fleet.get_all_vehicles_below_soc_level(0.1)))

  transactions = payment_engine.get_transactions()

  if store_results:
    transactions.to_csv(Path(output_folder, transaction_file), index = False)

  print(DemandFactory.counter)

run_single_simulation(end_time = 1500, n_cars = 1000, n_scooter = 100, n_kick_scooter = 100, seed = 42, substitution = 0.1)
# run_single_simulation(end_time = 600, n_cars = 1000, n_scooter = 1000, n_kick_scooter = 1000, seed = 42, substitution = 0.05)
# run_single_simulation(end_time = 600, n_cars = 1000, n_scooter = 1000, n_kick_scooter = 1000, seed = 42, substitution = 0.1)
# run_single_simulation(end_time = 600, n_cars = 1000, n_scooter = 1000, n_kick_scooter = 1000, seed = 42, substitution = 0.2)
# run_single_simulation(end_time = 600, n_cars = 1000, n_scooter = 1000, n_kick_scooter = 1000, seed = 42, substitution = 0.3)

# run_single_simulation(end_time = 600, n_cars = 1000, n_scooter = 1000, n_kick_scooter = 1000, seed = 1025)
# run_single_simulation(end_time = 600, n_cars = 1000, n_scooter = 1000, n_kick_scooter = 1000, seed = 1)
# run_single_simulation(end_time = 600, n_cars = 1000, n_scooter = 1000, n_kick_scooter = 1000, seed = 123)

# run_single_simulation(end_time = 60, n_cars = 200, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 300, n_scooter = 0, n_kick_scooter = 0)
# run_single_simulation(end_time = 60, n_cars = 400, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 500, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 600, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 700, n_scooter = 0, n_kick_scooter = 0)
#run_single_simulation(end_time = 60, n_cars = 800, n_scooter = 0, n_kick_scooter = 0)

# run_single_simulation(end_time = 60, n_cars = 200, n_scooter = 0, n_kick_scooter = 0)
