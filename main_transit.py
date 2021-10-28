import ast
import configparser
import datetime
from configparser import ConfigParser
from copy import deepcopy

import geopandas as gpd
import logging

from matplotlib import pyplot as plt
import numpy
import os
import pandas as pd
from pathlib import Path
import simpy
import sys

import tensorflow as tf
from tensorboard import program
from tqdm import tqdm


from simulation.agent.action_space import ActionSpace
from simulation.agent.episodic_semi_gradient_sarsa import ValueFunctionApproximator, EpisodicSemiGradientSarsa
from simulation.agent.episodic_semi_gradient_n_step_sarsa import EpisodicSemiGradientNStepSarsa
from simulation.agent.deep_q_learning import DQN, ModifiedTensorBoard
from simulation.agent.user import User # must come before DemandFactory, otherwise circular imports
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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Configuration from ini file.       #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

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

# Output Config
output_folder = parser.get("OUTPUT", "output_folder")

# Operator Config
transit_planning_lookahead = parser.get("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD")
transit_max_busses = parser.get("TRANSIT_OPERATOR", "MAX_BUSSES")

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

# Bus RL Agent Config
algo = parser.get("BUS", "AGENT")
try:
    nn_weights = parser.get("BUS", "WEIGHTS_PATH")
except configparser.NoOptionError:
    nn_weights = None
try:
    corridor = parser.get("BUS", "CORRIDOR_PATH")
except configparser.NoOptionError:
    corridor = None
episodes = int(parser.get("BUS", "EPISODES"))
actions = parser.get("BUS", "ACTION_SPACE").split(',')
action_dim = len(actions)
action_resolution = parser.get("BUS", "ACTION_SPACE_RESOLUTION")
agent_alpha = parser.get("BUS", "ALPHA")
agent_eps = parser.get("BUS", "EPS")
agent_gamma = parser.get("BUS", "GAMMA")
bootstrap_agent_n = parser.get("BUS", "N")
agent_penalty = int(parser.get("BUS", "PENALTY"))
q_net_layers = ast.literal_eval(parser.get("BUS", "DQN_LAYERS"))

# Custom tensorboard object
logdir = f'./data/output/logs/{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
tensorboard = ModifiedTensorBoard(log_dir=logdir)
# debugging slows down tensorflow a lot, so be careful
# tf.debugging.experimental.enable_dump_debug_info(logdir, tensor_debug_mode="FULL_HEALTH", circular_buffer_size=-1)

user_config = UserConfig(spatial_strategy, max_waiting_time)
transit_operator_config = TransitOperatorConfig(transit_planning_lookahead, transit_max_busses)
bus_agent_config = TransitAgentConfig(action_resolution, agent_alpha, agent_eps, agent_gamma, bootstrap_agent_n,
                                      tensorboard, corridor, agent_penalty, q_net_layers)

global_config.add_user_config(user_config)
global_config.add_transit_operator_config(transit_operator_config)
global_config.add_transit_agent_config(bus_agent_config)

track = parser.getboolean("OUTPUT", "TRACK_AGENT")

# Log Level
log_level = parser.get("SETTINGS", "log_level")

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Configure Logging.                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

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

logging.info(f'Tensorboard logdir: {logdir}',
             extra={"clazz": __name__, "oid": ""})

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


def run_single_simulation(start_time = 0, end_time = 60, seed = 4711, weights = None, replay_buffer = None, target_net_update_counter = 0):

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
    DemandFactory.counter = 0
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
    # q_hat = ValueFunctionApproximator(state_dim = 2, action_dim = 7, init_values = weights)
    # rl_agent = eval(algo+"(env, q_hat)") # this must be one of the worst ways to switch classes, mea culpa
    # rl_agent = DQN(env, weights)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. Simulation Modules.               #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Operator Modules
    operator = PublicTransitOperator(env, timetable, weights, replay_buffer, target_net_update_counter)
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
    print("Total Fulfilled Trips: " + str(payment_engine.total_fulfilled_trips))
    print("Total Missed Trips: " + str(payment_engine.total_missed_trips))
    try:
        service_level = payment_engine.total_fulfilled_trips / \
                        (payment_engine.total_missed_trips+payment_engine.total_fulfilled_trips)
    except ZeroDivisionError:
        service_level = 0
    print("Service Level: " + str(service_level))
    print("Passengers still in Bus (not dropped off): " + str(operator.unserved_passengers))

    return operator, world, service_level


# the experiment=None hack is to ensure a range works as well for pqdm
def run(experiment=None, **kwargs):
    if kwargs:
        for k, v in kwargs.items():
            if k == 'penalty':
                logging.info(f'Agent Penalty set to {str(v)}',
                             extra={"clazz": __name__, "oid": ""})
                bus_agent_config.penalty = v
            if k == 'q_net_layer':
                logging.info(f'DQN layer configuration set to {str(v)}',
                             extra={"clazz": __name__, "oid": ""})
                bus_agent_config.q_net_layer = v

        # list experiment params for paths
        experiments = "_".join([str(k)+"="+str(v) for k, v in kwargs.items()])

        logdir_ = f'{logdir}/{experiments}'
        tensorboard_ = ModifiedTensorBoard(log_dir=logdir_)
        bus_agent_config.tensorboard = tensorboard_

    if experiment is not None:
        # average experiment is running
        logdir_ = f'{logdir}/run{experiment}'
        tensorboard_ = ModifiedTensorBoard(log_dir=logdir_)
        bus_agent_config.tensorboard = tensorboard_

    w = nn_weights # weights
    b = None # replay buffer
    c = 0 # update counter
    episode_returns = []

    for i in tqdm(range(episodes), total=episodes):

        operator, world, service_level = run_single_simulation(
            start_time=15*60, end_time=16.1*60, weights=w, replay_buffer=b, target_net_update_counter=c)

        if len(operator._rl_agent_replay_buffer) >= 1000:
            logging.debug(f'Episode {str(i)}: Training happened.')

        if not kwargs:
            episode_returns.append(deepcopy({'episode': i,
                                             'return': operator._rewards_sum[-1],
                                             'service_level': service_level}))
        else:
            # extend return by experiment parameters
            episode_returns.append({**kwargs,
                                    **deepcopy({'episode': i,
                                                'return': operator._rewards_sum[-1],
                                                'service_level': service_level})})
        w = operator._rl_agent_weights
        b = operator._rl_agent_replay_buffer
        c = operator._rl_agent_update_counter

        if track:
            import folium
            from folium import GeoJson
            from folium.plugins import TimestampedGeoJson

            t = TimestampedGeoJson({
                'type': 'FeatureCollection',
                'features': [
                    operator._timestamped_position
                ]
            }, loop=False, period='PT1M')

            template = """{
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': c,
                },
                'properties': {
                    'color': 'red'
                }
            }"""

            d = GeoJson({
                'type': 'FeatureCollection',
                'features':[eval(template) for c in operator._tracked_demands]
            }, style_function=lambda x:{'color': 'red'})

            m = folium.Map(location=[52.52, 13.40])

            d.add_to(m)
            t.add_to(m)
            if not kwargs:
                m.save(os.path.join(output_folder, 'tracking', f'bus_movement_episode_{str(i)}.html'))
            else:
                m.save(os.path.join(output_folder, 'tracking', f'bus_movement_episode_{str(i)}_{experiments}.html'))

    if not kwargs:
        weights_path = f'{str(episodes)}_episodes_weights_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.keras'
    else:
        weights_path = f'{str(episodes)}_episodes_{experiments}_experiment_weights_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.keras'

    operator._rl_agent_model.save_weights(
        os.path.join(output_folder, weights_path)
    )

    returns = pd.DataFrame.from_records(episode_returns)
    returns = returns.set_index(returns['episode'])[['return', 'service_level']]
    if not kwargs:
        returns.plot(secondary_y=['service_level'],
                     alpha=.5,
                     color=['black', 'green'],
                     title='Total Reward and Service Level over Episodes')
    else:
        returns.plot(secondary_y=['service_level'],
                     alpha=.5,
                     color=['black', 'green'],
                     title=f'Experiment: {experiments}')
    plt.show()

    return returns


if __name__ == '__main__':
    run()
