##Imports
# Standard library imports
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Third-party library imports
import simpy

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.config_reader import ConfigReader

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    Configuration,
    ModeChoiceStrategy,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)

# Import operator related modules
from simulation.operator.fleet_factory import (
    generate_mixed_ride_hailing_fleet,
    generate_ridehailing_fleet_config,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine

# Import vehicle types and vehicle choice options
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import (
    OnlyCarVehicleChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking

# Custom module imports
from utils import load_geodesic_environment

# Change working directory to path of this file
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Initialize an empty Configuration object
config = Configuration.instance()

# Initialize ConfigReader with the configuration file and the Configuration object
config_reader = ConfigReader(sys.argv[1])
config_reader.load_config()

# make a copy of the used config file that references this run
output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d_%H:%M:%S")
if not os.path.exists("data/output/configs"):
    os.makedirs("data/output/configs")
shutil.copy(sys.argv[1], f"data/output/configs/{output_timestamp}.ini")


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)

logger = logging.getLogger()
logger.setLevel(config.log_level)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s"
)
file_handler = logging.FileHandler("report.log")
file_handler.setFormatter(formatter)
file_handler.setLevel(config.file_log_level)
logger.addHandler(file_handler)

# Add Custom Init Filters (which work without the ENV obj)
cf = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Basic Configuration                     #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


mode_choice_strategy = config.get_mode_choice_config().mode_choice_strategy
if mode_choice_strategy == ModeChoiceStrategy.SUBSTITUTION_AWARE:
    vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
        ["AutonomousCar", "RideHailingCar"]
    )  ## Needs to be modified depending on the modus
else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####

#### Not sure if this part is necessary #####
MoD_interval_reduction = 0  # By choice
config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=0)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
edf = ExtraDefaultFilter(filter_name="add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)

# Population Type
# TODO: Generate population for multiple modes at once --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/52
population_factory = PopulationFactory(
    config.ride_hailing_population_probabilities, config.seed
)

# Load Spatial Environment

load_geodesic_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

tracking = Tracking.init(env)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Charging Infrastructure                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

charging_infrastructure = ChargingInfrastructure(
    env=env,
    location_list=config.get_charging_infrastructure_config().locations,
    power_list=config.get_charging_infrastructure_config().power,
    capacity_list=config.get_charging_infrastructure_config().capacity,
    queue_size=config.get_charging_infrastructure_config().queue_size,
    reset=True,
)

#### End Charging Infrastructure Configuration #####


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Demand Data (once).                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

p = Path(config.trip_demand_file)
di = DemandImporter(
    spatial_resolution=config.spatial_resolution,
    temporal_resolution=config.temporal_resolution,
    daily_resolution=config.daily_resolution,
    city=config.city,
)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(
    f"hex_{config.spatial_resolution.value}"
).index.tolist()
dmi = DistanceMatrixImporter(
    hexagons, config.spatial_resolution.value, "./data/infrastructure", config.city
)
distance_matrix = dmi.load_distance_matrix()


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Reset counters and random number        #
# generators before each run              #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

User.user_id = 0
DemandFactory.counter = 0
# Add a counter for ridehailing car too

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Configure and generate / spawn fleet vehicles
# Ride Hailing Fleet

search_engine = {
    "ride_hailing_0": RideHailingSearchEngine(env),
    "ride_hailing_1": RideHailingSearchEngine(env),
}

vehicle_assignment_engine = {
    "ride_hailing_0": RideHailingAllocationEngine(env),
    "ride_hailing_1": RideHailingAllocationEngine(env),
}

available_vehicle_modes_ridehailing = ["RideHailingCar", "AutonomousCar"]
available_vehicle_modes_supply_ride_hailing = [
    config.ridehailing_operator_config.n_ridehailing_cars,
    config.ridehailing_operator_config.n_autonomous_cars,
]

# Get the supply probability from supply file
supply_prob = pd.read_csv(config.vehicle_supply_file)

ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=config.ridehailing_operator_config.n_ridehailing_cars,
    n_AVs=config.ridehailing_operator_config.n_autonomous_cars,
    allocation_method="historical",
    allocation=config.ridehailing_operator_config.allocation,
)
ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_0
)

ride_hailing_fleet_config_1 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=config.ridehailing_operator_config.n_ridehailing_cars,
    n_AVs=config.ridehailing_operator_config.n_autonomous_cars,
    allocation_method="historical",
    allocation=config.ridehailing_operator_config.allocation,
)
ride_hailing_fleet_1 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_1
)

# Add the fleet to the search engine
search_engine["ride_hailing_0"].register_fleet(ride_hailing_fleet_0)
search_engine["ride_hailing_1"].register_fleet(ride_hailing_fleet_1)

# Initialize fleet operations

# if queue sizes at charging stations are all zero, we should account for that in the operations
# there can be more clever and nuanced approaches, but as a rule of thumb, we should not allow operations to send vehicles to charging stations that are full if we don't allow queueing
allow_queue = sum(config.get_charging_infrastructure_config().queue_size) > 0

ridehailing_operations_0 = RideHailingBaseChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=config.ridehailing_operator_config.operations_start,
    operation_duration=config.ridehailing_operator_config.operations_duration,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ridehailing_operator_config.recharge_threshold,
    allow_queue=allow_queue,
)

ridehailing_operations_1 = RideHailingBaseChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=config.ridehailing_operator_config.operations_start,
    operation_duration=config.ridehailing_operator_config.operations_duration,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ridehailing_operator_config.recharge_threshold,
    allow_queue=allow_queue,
)

# Initialize operators

ridehailing_operator_0 = RideHailingOperator(
    env=env,
    fleet=ride_hailing_fleet_0,
    charging_infrastructure=charging_infrastructure,
    operations=ridehailing_operations_0,
    search_engine=search_engine["ride_hailing_0"],
    allocation_engine=vehicle_assignment_engine["ride_hailing_0"],
)

ridehailing_operator_1 = RideHailingOperator(
    env=env,
    fleet=ride_hailing_fleet_1,
    charging_infrastructure=charging_infrastructure,
    operations=ridehailing_operations_1,
    search_engine=search_engine["ride_hailing_1"],
    allocation_engine=vehicle_assignment_engine["ride_hailing_1"],
)

payment_engine = {
    "ride_hailing_0": ridehailing_operator_0,
    "ride_hailing_1": ridehailing_operator_1,
}

# Initialize task queues
task_queue_ridehailing = TaskQueue(env)

# Initialize World
world = World.init(
    env,
    search_engine,
    payment_engine,
    vehicle_assignment_engine,
    vehicle_choice_model,  # Again the problem with different modes is here
    population_factory,
    charging_infrastructure,
    reset=True,
)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Spawn Demand Processes.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: we need to have a look at https://github.com/IS3UniCologne/urban-mobility-simulation/issues/32
# for now, we spawn by chance
demand_factory = DemandFactory(
    env,
    demand_profile,
    di,
    world,
    config.demand_modifier_files,
    config.seed,
    mode="ride_hailing",
)
# env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

# env.run(until=50)

# logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})


# For multiple simulation runs
def run_simulation(end_time, seed=4711, env=env):
    # Before a new simulation run, reset everything
    User.user_id = 0
    DemandFactory.counter = 0

    # Inject Simulation Environment to Logger (such that we can log the env time)
    cf = SimulationContextFilter(filter_name="add_env", extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    # Use only if the configuration parameters stay unchanged to avoid reloading everytime. Reload demand factory if the demand profile is different between consecutive runs
    demand_factory.reset()

    env.process(demand_factory.generate_demand())

    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    env.run(until=end_time)

    logging.warning("Ending Simulation.", extra={"clazz": "main", "oid": ""})


env = simpy.Environment(config.start_time)
run_simulation(end_time=config.end_time)
