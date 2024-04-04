# This files provided a template for a simulation with a public transport operator
# Imports
import os
import sys
import configparser
from pathlib import Path
from configparser import ConfigParser
from learning.spaces.action_space import DiscreteActionSpace
from learning.dynamic_bus_checkpoints import DynamicBusCheckpointProblem

# Change working directory to path of main.py
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read command line arguments using ConfigParser
parser = ConfigParser()
parser.read(sys.argv[1])

# Extract experiment management parameters from the configuration file
start_time = parser.getint("EXPERIMENT_MANAGEMENT", "START_TIME")
end_time = parser.getint("EXPERIMENT_MANAGEMENT", "END_TIME")
seed = parser.getint("EXPERIMENT_MANAGEMENT", "SEED")

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Configuration                           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Imports
import numpy as np
import pandas as pd
from simulation.agent.user import User  
from simulation.helper.configuration.configuration import Configuration, ChargingInfrastructureConfig, UserConfig, DynamicCheckpointRoutingConfig
from simulation.infrastructure.charging_stations.charging_infastructure import ChargingInfrastructure
from simulation.helper.configuration.configuration import ModeChoiceConfig
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.vehicle import Vehicle
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from simulation.agent.user import User  # must come before DemandFactory, otherwise circular imports
from simulation.world.demand.demand_factory import DemandFactory
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.infrastructure.helper.timetable import Timetable
from simulation.helper.configuration.configuration import BusConfig
from simulation.helper.configuration.configuration import TransitOperatorConfig
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.vehicle_choice_model.public_transit_vehicle_choice_behavior import PublicTransitVehicleChoiceBehavior


# World / Resolution Config
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
city = parser.get("WORLD", "city")

# Create a global configuration object
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

# Load input files and configurations related to demand, supply, and infrastructure
## Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Public Transit Operator / Timetable)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# User and Mode Choice Configuration
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(',')
pop_prob = parser.get("MODE_CHOICE_MODEL", "population_probabilities").split(',')
pop_prob = [float(x) for x in pop_prob]
MoD_interval_reduction = 0 # By choice

# Vehicle Choice Model
vehicle_choice_model = PublicTransitVehicleChoiceBehavior(['Bus'])

# Create mode choice configuration object
mc = ModeChoiceConfig(mode_choice_strategy, mode_choice_sub_boundary, mode_choice_available_modes,
                      mode_choice_model_path)

# User Config
user_config = UserConfig(
    spatial_strategy=parser.get("USER", "SPATIAL_STRATEGY"),
    max_wait=parser.getint("USER", "TRANSIT_MAX_WAIT")
)
# Load bus and transit operator configurations
## Bus Vehicle Config
bus_config = BusConfig(
    max_available_seats=parser.getint("BUS", "SEATS"),
    velocity=parser.getfloat("BUS", "VELOCITY")
)
## Public Transit Operator Config
transit_operator_config = TransitOperatorConfig(
    planning_lookahead=parser.getint("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD"),
    max_busses=parser.getint("TRANSIT_OPERATOR", "MAX_BUSSES")
)

# Problem Config
try:
    corridor = parser.get("DYNAMIC_CHECKPOINT_ROUTING", "CORRIDOR_PATH")
except configparser.NoOptionError:
    corridor = None

dynamic_checkpoint_routing_config = DynamicCheckpointRoutingConfig(
    action_resolution=parser.getint("DYNAMIC_CHECKPOINT_ROUTING", "ACTION_SPACE_RESOLUTION"),
    action_space=DiscreteActionSpace(parser.get("DYNAMIC_CHECKPOINT_ROUTING", "ACTION_SPACE").split(',')),
    checkpoints=[int(x) for x in parser.get("DYNAMIC_CHECKPOINT_ROUTING", "CHECKPOINTS").split(',')],
    corridor=corridor,
    penalty_checkpoints=parser.getfloat("DYNAMIC_CHECKPOINT_ROUTING", "PENALTY_CHECKPOINTS"),
    penalty_goingback=parser.getint("DYNAMIC_CHECKPOINT_ROUTING", "PENALTY_GOINGBACK"),
    penalty_unreachable=parser.getint("DYNAMIC_CHECKPOINT_ROUTING", "PENALTY_UNREACHABLE"),
    periodic_testing=parser.getint("DYNAMIC_CHECKPOINT_ROUTING", "PERIODIC_TESTING", fallback=None),
    reward=parser.getint("DYNAMIC_CHECKPOINT_ROUTING", "REWARD"),
    timelimit_multiplier=parser.getfloat("DYNAMIC_CHECKPOINT_ROUTING", "TIMELIMIT"),
    use_learning_agent=False
)
# Register configurations to the global configuration object
global_config.add_user_config(user_config)
global_config.add_mode_choice_config(mc)
global_config.add_bus_config(bus_config)
global_config.add_transit_operator_config(transit_operator_config)
global_config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction) # Not sure if we need this
global_config.add_dynamic_checkpoint_routing_config(dynamic_checkpoint_routing_config)



# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Imports
import simpy
import geopandas as gpd
from utils import load_environment
from simulation.world.population.PopulationFactory import PopulationFactory

# Before each simulation run, reset counter and random number generators
Bus.bus_id = 0
User.user_id = 0
DemandFactory.counter = 0
Vehicle.vehicle_id = 0
PublicTransitVehicle.public_transit_vehicle_id = 0

# Initialize simulation environment using SimPy
env = simpy.Environment(initial_time=0)

# Population Type
## Load environment and create a population using the specified probability distribution
population_factory = PopulationFactory(pop_prob, seed)

# Load Spatial Environment
load_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
timetable = Timetable(transit_timetable_path)
timetable.import_timetable()
pt_operator = PublicTransitOperator(env, timetable)
search_engine = {'public_transport': pt_operator}
payment_engine = search_engine
vehicle_assignment_engine = {'public_transport': pt_operator}

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Operations Management Processes         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# There are not busses to pick up 
# Store Tasks which are processed by service workers
#from simulation.operator.operations_management.task_queue import TaskQueue
#task_queue_operator = TaskQueue(env)

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

# Load distance matrix for geospatial calculations
geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(f"hex_{spatial_res}").index.tolist()
dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure", city)
distance_matrix = dmi.load_distance_matrix()
GeodesicEnvironment.getInstance().reset_random_generator(4711)

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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
import logging

# Log Level
log_level = parser.get("SETTINGS", "log_level")

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

# Initialize tracking module for simulation
tracking = Tracking.init(env)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
# World
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.world import World
# world = World.init(env, search_engine, payment_engine, vehicle_assignment_engine,
#                        population_factory, reset=True)

# Following part does actually not have anything to do with the transit operator but is necessary to initialize world

 # Charging Infrastructure
number_of_charging_stations = parser.getint("Charging_Infrastructure", "NUMBER_OF_CHARGING_STATIONS")
charging_location_list = parser.get("Charging_Infrastructure", "BASE_REGIONS").split(',')[
                             :number_of_charging_stations]
    ### Activate it if there are specific capacity for charging stations
    # charging_power_list = parser.get("Charging_Infrastructure", "CHARGING_STATION_POWER").split(',')
    # charging_power_list = [float(x) for x in charging_power_list]
    # charging_capacity_list = parser.get("Charging_Infrastructure", "CHARGING_STATION_CAPACITY").split(',')
    # charging_capacity_list = [float(x) for x in charging_capacity_list]
charging_power = 50
charging_capacity = 20
charging_power_list = list(np.zeros(len(charging_location_list)) + charging_power)
charging_capacity_list = list(np.zeros(len(charging_location_list)) + charging_capacity)
sic = ChargingInfrastructureConfig(charging_location_list, charging_power_list, charging_capacity_list)
global_config.add_charging_infrastructure_config(sic)
charging_infrastructure = ChargingInfrastructure(env, charging_location_list, charging_power_list,
                                                     charging_capacity_list, reset=True)


world = World.init(env, search_engine, search_engine, vehicle_assignment_engine, vehicle_choice_model,
                       population_factory, charging_infrastructure, reset=True)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Spawn Demand Processes.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
import random
random_number = random.random()

# Needs to be modified depending on available options
silly_choice = 'public_transport'
demand_factory = DemandFactory(env, demand_profile, di, world, [], seed, mode=silly_choice)

#dynamic_checkpoint_routing_config.problem = DynamicBusCheckpointProblem(env)
# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# End Spawn Demand Processes.             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env.process(demand_factory.generate_demand())

## Run Simulation

logging.warning(f"Starting Simulation.",
                    extra={"clazz": "main", "oid": ""})

# Leave it for now. TransitUser is too hardcoded for dynamic checkpoint routing
env.run(until=10)

logging.warning(f"Simulation Finished.",
                extra={"clazz": "main", "oid": ""})