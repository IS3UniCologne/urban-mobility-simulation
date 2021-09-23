import numpy
from tqdm import tqdm
from matplotlib import pyplot as plt

from simulation.agent.action_space import ActionSpace
from simulation.agent.episodic_semi_gradient_sarsa import ValueFunctionApproximator
from simulation.agent.user import User
from simulation.helper.configuration.configuration import Configuration, UserConfig, TransitOperatorConfig, \
    TransitAgentConfig
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from simulation.vehicle.vehicle import Vehicle
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
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Input Files (Infrastructure)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")
# transit_shapes_path = parser.get("INFRASTRUCTURE", "path_transit_shapes")

# Operator Config
transit_planning_lookahead = parser.get("TRANSITOPERATOR", "TRANSIT_LOOKAHEAD")
transit_max_busses = parser.get("TRANSITOPERATOR", "MAX_BUSSES")

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

# Bus Agent Config
actions = parser.get("BUS", "ACTION_SPACE").split(',')
action_dim = len(actions)
action_resolution = parser.get("BUS", "ACTION_SPACE_RESOLUTION")
agent_alpha = parser.get("BUS", "ALPHA")
agent_eps = parser.get("BUS", "EPS")
agent_gamma = parser.get("BUS", "GAMMA")

user_config = UserConfig(spatial_strategy, max_waiting_time)
transit_operator_config = TransitOperatorConfig(transit_planning_lookahead, transit_max_busses)
bus_agent_config = TransitAgentConfig(action_resolution, agent_alpha, agent_eps, agent_gamma)

global_config.add_user_config(user_config)
global_config.add_transit_operator_config(transit_operator_config)
global_config.add_transit_agent_config(bus_agent_config)

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

    geodesic_environment = GeodesicEnvironment.getInstance()
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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Construct Action Space (once).          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
ActionSpace.init(actions)


def run_single_simulation(start_time = 0, end_time = 60, seed = 4711, q_hat_weights = None):

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Setup Simulation Environment.           #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Simulation Environment
    env = simpy.Environment(initial_time=start_time)

    # before a new simulation run, reset everything
    Vehicle.vehicle_id = 0
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
    # Setup Value Function Approximation      #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    q_hat = ValueFunctionApproximator(state_dim = 2, action_dim = 7, init_values = q_hat_weights)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. Simulation Modules.               #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Operator Modules
    operator = PublicTransitOperator(env, timetable, q_hat)
    search_engine = operator
    payment_engine = operator
    vehicle_assignment_engine = operator

    # Vehicle Choice Model
    vehicle_choice_model = PublicTransitVehicleChoiceBehavior(['Bus'])

    # World
    world = World.init(env, search_engine, search_engine, vehicle_assignment_engine, vehicle_choice_model, reset=True)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Spawn Demand Processes.                 #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    demand_factory = DemandFactory(env, demand_profile, di, world, demand_modifier_paths, seed)

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
    # print("Total Revenue: " + str(payment_engine.total_revenue))
    # print("Total Fulfilled Trips: " + str(payment_engine.total_fulfilled_trips))
    # print("Total Missed Trips: " + str(payment_engine.total_missed_trips))

    return {'states': operator._states, 'actions': operator._actions, 'rewards': operator._rewards, 'return': operator._rewards_cum, 'weights': q_hat.weights}


if __name__ == '__main__':
    EPISODES = 200

    w = [numpy.zeros(2 * action_dim)]
    metrics = {}
    for i in tqdm(range(EPISODES), total=EPISODES):
        out = run_single_simulation(start_time=15*60, end_time=17*60, q_hat_weights=w[-1])
        metrics[i] = out
        w.append(out['weights'])

    returns = pd.DataFrame.from_records([{'episode': i, 'return': x['return'][-1]} for i, x in metrics.items()])
    returns.plot(x='episode', y='return')
    plt.show()
