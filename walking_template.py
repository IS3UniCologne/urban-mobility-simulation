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
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.operator.walking_search_engine import WalkingSearchEngine

# Custom module imports
from simulation.vehicle.walking import Walking

# Import vehicle types and vehicle choice options
from simulation.vehicle_choice_model.only_walking_choice_behavior import (
    OnlyWalkingChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking
from utils import load_environment

# Change working directory to path of this file
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
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

### Input Files
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

pop_prob_sharedvehicle = 0

mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")

mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(",")

mc = ModeChoiceConfig(
    mode_choice_strategy,
    mode_choice_sub_boundary,
    mode_choice_available_modes,
    mode_choice_model_path,
)

global_config.add_mode_choice_config(mc)

if mode_choice_strategy == "substitution":
    vehicle_choice_model = OnlyWalkingChoiceBehavior(["Walking"])
else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=0)

# Population Type
population_factory = PopulationFactory(pop_prob_sharedvehicle, seed)

# Load Spatial Environment
load_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Output Configuration                    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

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
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Log Level
log_level = parser.get("SETTINGS", "log_level")


# Make it beautiful
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

GeodesicEnvironment.getInstance().reset_random_generator(4711)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Reset counters and random number        #
# generators before each run              #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

User.user_id = 0
Walking.walking_id = 0
DemandFactory.counter = 0

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Operator Modules
search_engine = {"walking": WalkingSearchEngine(env)}

payment_engine = search_engine

vehicle_assignment_engine = {"walking": None}

# Initialize World
world = World.init(
    env,
    search_engine,
    payment_engine,
    vehicle_assignment_engine,
    vehicle_choice_model,  # Again the problem with different modes is here
    population_factory,
    None,
    reset=True,
)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Spawn Demand Processes.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

demand_factory = DemandFactory(env, demand_profile, world, [], seed, mode="walking")
env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

env.run(until=50)

logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})
