import ast
import configparser
import datetime
import logging
import os
import pickle
import sys
from collections import deque
from configparser import ConfigParser
from copy import deepcopy
from pathlib import Path

import pandas as pd
import simpy
from matplotlib import pyplot as plt
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from learning.agents.DQN_torch import DQN
from learning.dynamic_bus_checkpoints import DynamicBusCheckpointProblem

# from learning.helper.modified_tensor_board import ModifiedTensorBoard
from learning.spaces.action_space import DiscreteActionSpace
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import (
    BusConfig,
    Configuration,
    DQNConfig,
    DynamicCheckpointRoutingConfig,
    TransitOperatorConfig,
    UserConfig,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.infrastructure.helper.timetable import Timetable
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from simulation.vehicle.vehicle import Vehicle
from simulation.vehicle_choice_model.public_transit_vehicle_choice_behavior import (
    PublicTransitVehicleChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking
from utils import load_environment

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
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
city = parser.get("WORLD", "city")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city)

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Input Files (Infrastructure)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")

# Output Config
output_folder = parser.get("OUTPUT", "output_folder")

# User Config
user_config = UserConfig(
    spatial_strategy=parser.get("USER", "SPATIAL_STRATEGY"),
    max_wait=parser.getint("USER", "TRANSIT_MAX_WAIT"),
)

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

# Custom tensorboard object
logtime = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
logdir = f"./data/output/logs/{logtime}"

# PyTorch
tensorboard = SummaryWriter(logdir)

# Tensorflow
# tensorboard = ModifiedTensorBoard(log_dir=logdir)
# debugging slows down tensorflow a lot, so be careful
# tf.debugging.experimental.enable_dump_debug_info(logdir, tensor_debug_mode="FULL_HEALTH", circular_buffer_size=-1)

# RL Agent Config
try:
    tau = parser.getfloat("DQN", "TAU")
except configparser.NoOptionError:
    tau = None

try:
    # warm start the replaybuffer with pure exploration
    replaybuffer_path = parser.get("DQN", "REPLAYBUFFER")
    with open(replaybuffer_path, "rb") as f:
        replaybuffer = pickle.load(f)
        replaybuffer = deque(replaybuffer, maxlen=len(replaybuffer))
except configparser.NoOptionError:
    replaybuffer = None

DQN_config = DQNConfig(
    alpha=parser.getfloat("DQN", "ALPHA"),
    batchsize=parser.getint("DQN", "BATCHSIZE"),
    buffersize=parser.getint("DQN", "BUFFERSIZE"),
    episode=1,
    episodes=parser.getint("DQN", "EPISODES"),
    eps=parser.getfloat("DQN", "EPS"),
    eps_decay_strategy=parser.get("DQN", "EPS_DECAY_STRATEGY"),
    eps_decay=parser.getfloat("DQN", "EPS_DECAY"),
    eps_max=parser.getfloat("DQN", "EPS_MAX"),
    eps_min=parser.getfloat("DQN", "EPS_MIN"),
    double_q=parser.getboolean("DQN", "USE_DOUBLE_Q"),
    gamma=parser.getfloat("DQN", "GAMMA"),
    lr_decay=parser.getboolean("DQN", "LR_DECAY"),
    lr_decay_steps=parser.getint("DQN", "LR_DECAY_STEPS"),
    min_experience=(
        parser.getint("DQN", "MIN_EXPERIENCE") if replaybuffer is None else 0
    ),
    q_net_layer=ast.literal_eval(parser.get("DQN", "DQN_LAYERS")),
    replaybuffer=replaybuffer,
    target_update_threshold=parser.getint("DQN", "TARGET_UPDATE_THRESHOLD"),
    tau=tau,
    tensorboard=tensorboard,
    train_frequency=parser.getint("DQN", "TRAIN_FREQUENCY"),
    weights=None,
)

# Problem Config
try:
    corridor = parser.get("DYNAMIC_CHECKPOINT_ROUTING", "CORRIDOR_PATH")
except configparser.NoOptionError:
    corridor = None

dynamic_checkpoint_routing_config = DynamicCheckpointRoutingConfig(
    action_resolution=parser.getint(
        "DYNAMIC_CHECKPOINT_ROUTING", "ACTION_SPACE_RESOLUTION"
    ),
    action_space=DiscreteActionSpace(
        parser.get("DYNAMIC_CHECKPOINT_ROUTING", "ACTION_SPACE").split(",")
    ),
    checkpoints=[
        int(x)
        for x in parser.get("DYNAMIC_CHECKPOINT_ROUTING", "CHECKPOINTS").split(",")
    ],
    corridor=corridor,
    penalty_checkpoints=parser.getfloat(
        "DYNAMIC_CHECKPOINT_ROUTING", "PENALTY_CHECKPOINTS"
    ),
    penalty_goingback=parser.getint("DYNAMIC_CHECKPOINT_ROUTING", "PENALTY_GOINGBACK"),
    penalty_unreachable=parser.getint(
        "DYNAMIC_CHECKPOINT_ROUTING", "PENALTY_UNREACHABLE"
    ),
    periodic_testing=parser.getint(
        "DYNAMIC_CHECKPOINT_ROUTING", "PERIODIC_TESTING", fallback=None
    ),
    reward=parser.getint("DYNAMIC_CHECKPOINT_ROUTING", "REWARD"),
    timelimit_multiplier=parser.getfloat("DYNAMIC_CHECKPOINT_ROUTING", "TIMELIMIT"),
    use_learning_agent=True,
)

global_config.add_user_config(user_config)
global_config.add_transit_operator_config(transit_operator_config)
global_config.add_bus_config(bus_config)
global_config.add_DQN_config(DQN_config)
global_config.add_dynamic_checkpoint_routing_config(dynamic_checkpoint_routing_config)

# Log Level
log_level = parser.get("SETTINGS", "log_level")

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Configure Logging.                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)
logging.raiseExceptions = False
logger = logging.getLogger()
logger.setLevel(log_level)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)

# Add Custom Init Filters (which work without the ENV obj)
cf_init = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf_init)

logging.debug(f"Tensorboard logdir: {logdir}")  # noqa: G004

# 1. Initialize Simulation and simpy Environment
# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Underlying Spatial Environment.    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

load_environment()

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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timetable = Timetable(transit_timetable_path)
timetable.import_timetable()


def run_simulation(start_time: int, end_time: int, seed=4711):  # noqa: ANN001, ANN201
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
    cf = SimulationContextFilter(filter_name="add_env", extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. Tracking                          #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    Tracking.init(env)

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
    vehicle_choice_model = PublicTransitVehicleChoiceBehavior(["Bus"])

    # Population Type
    price_sensitive_pop_prob = 0  # TODO: move to user config
    population_factory = PopulationFactory(price_sensitive_pop_prob, seed)

    # World
    world = World.init(
        env,
        search_engine,
        search_engine,
        vehicle_assignment_engine,
        vehicle_choice_model,
        population_factory,
        charging_infrastructure=None,
        reset=True,
    )

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Spawn Demand Processes.                 #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    demand_factory = DemandFactory(
        env,
        demand_profile,
        di,
        world,
        demand_modifier_paths,
        seed,
        mode="public_transport",
    )
    env.process(demand_factory.generate_demand())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. RL Abstraction                    #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    # TODO: problem and agent can be initialized once outside the simulation and only reset
    # (Re-)Initialize the abstraction layer of the problem
    dynamic_checkpoint_routing_config.problem = DynamicBusCheckpointProblem(env)

    # Initialize Generalized Learning Agent with Problem
    dynamic_checkpoint_routing_config.learning_agent = DQN(
        problem=dynamic_checkpoint_routing_config.problem
    )
    # learning_agent_uid = tracking.register(dynamic_routing_config.learning_agent)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Run Simulation.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    env.run(until=end_time)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Benchmarks.                             #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    try:
        service_level = payment_engine.total_fulfilled_trips / (
            payment_engine.total_missed_trips + payment_engine.total_fulfilled_trips
        )
    except ZeroDivisionError:
        service_level = 0
    # print("Total Fulfilled Trips: " + str(payment_engine.total_fulfilled_trips))
    # print("Total Missed Trips: " + str(payment_engine.total_missed_trips))
    # print("Service Level: " + str(service_level))
    # print("Passengers still in Bus (not dropped off): " + str(operator._unserved_passengers))

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # The RL related stuff is automatically   #
    # retained in the config.                 #
    #                                         #
    # Tracking related stuff is handled by    #
    # DynamicBusTracking.                     #
    #                                         #
    # We only need to handle performance KPIs #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # return problem evaluation measures
    return (
        dynamic_checkpoint_routing_config.problem.reached_destination,
        dynamic_checkpoint_routing_config.problem.distance,
        dynamic_checkpoint_routing_config.problem.duration,
        service_level,
    )


episodes = []

for e in tqdm(range(DQN_config.episodes)):
    logging.debug(
        f"Starting Episode {DQN_config.episode}",  # noqa: G004
        extra={"clazz": "Main Routine"},
    )

    if (
        dynamic_checkpoint_routing_config.periodic_testing is not None
        and DQN_config.episode % dynamic_checkpoint_routing_config.periodic_testing == 0
    ):
        DQN_config.evaluation = True

    reached_destination, distance, duration, service_level = run_simulation(
        start_time=14 * 60, end_time=16 * 60
    )

    episode = deepcopy(
        {
            "episode": DQN_config.episode,
            "evaluation": DQN_config.evaluation,
            "return": dynamic_checkpoint_routing_config.learning_agent._cumulative_reward,  # noqa: SLF001
            "service_level": service_level,
            "reached_destination": reached_destination,
            "distance": distance,
            "duration": duration,
        }
    )
    episodes.append(episode)

    # reset, just in case
    DQN_config.evaluation = False

    if DQN_config.episode == DQN_config.episodes:
        break
    else:
        DQN_config.episode += 1

episodes = pd.DataFrame.from_records(episodes)
episodes = episodes.set_index("episode")

print(episodes.tail(20))  # noqa: T201
episodes.to_csv(f"./data/output/returns/{logtime}.csv")
logging.info(f"Tensorboard logdir: {logdir}", extra={"clazz": "Main Routine"})  # noqa: G004
logging.info(
    f"Episode Returns: {f'./data/output/returns/{logtime}.csv'}",  # noqa: G004
    extra={"clazz": "Main Routine"},
)

fig, ax = plt.subplots()
ax.plot(episodes.index, episodes["return"], alpha=0.5, color="lightblue")
ax.plot(
    episodes[episodes["evaluation"]].index,
    episodes[episodes["evaluation"]]["return"],
    color="darkblue",
)
ax2 = ax.twinx()
ax2.plot(episodes.index, episodes["service_level"], alpha=0.5, color="lightgreen")
ax2.plot(
    episodes[episodes["evaluation"]].index,
    episodes[episodes["evaluation"]]["service_level"],
    color="darkgreen",
)
plt.show()

# with open(f'replaybuffer_torch_500_goingback.pkl', 'wb') as f:
#     pickle.dump(DQN_config.replaybuffer, f, protocol=pickle.HIGHEST_PROTOCOL)
