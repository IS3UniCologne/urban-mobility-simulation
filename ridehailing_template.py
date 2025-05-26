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

# Initialize Configuration
config = Configuration()

# make a copy of the used config file that references this run
output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
output_config_dir = os.path.normpath(os.path.join("data", "output", "configs"))
if not os.path.exists(output_config_dir):
    os.makedirs(output_config_dir)
shutil.copy(sys.argv[1], os.path.join(output_config_dir, f"{output_timestamp}.toml"))


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Disable the default handler of the root logger
logging.getLogger().handlers.clear()

logger = logging.getLogger()
# Set to logging.DEBUG to see all logs
logger.setLevel(logging.DEBUG)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s"
)

# Create a console handler with its own level (LOG_LEVEL)
console_handler = logging.StreamHandler()
console_handler.setLevel(config.settings.LOG_LEVEL)
console_handler.setFormatter(formatter)


output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
logs_dir = os.path.normpath(os.path.join(config.path.OUTPUT_FOLDER, "logs"))
# Create directory for logs if not exists
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
log_file = os.path.join(logs_dir, f"{output_timestamp}.log")
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)
file_handler.setLevel(config.settings.FILE_LOG_LEVEL)


logger.addHandler(console_handler)
logger.addHandler(file_handler)

edf = ExtraDefaultFilter(filter_name="add_default_value")
logger.addFilter(edf)

# Add Custom Init Filters (which work without the ENV obj)
cf = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf)


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Basic Configuration                     #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

mode_choice_strategy = config.mode_choice_model.MODE_CHOICE_STRATEGY
if mode_choice_strategy == ModeChoiceStrategy.SUBSTITUTION_AWARE:
    vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
        ["AutonomousCar", "RideHailingCar"]
    )  ## Needs to be modified depending on the modus
else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=0)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
logger.addFilter(cf)

# Population Type
# TODO: Generate population for multiple modes at once --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/52
population_factory = PopulationFactory(
    config.population.RIDE_HAILING_POPULATION_PROBABILITIES
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
    location_list=config.charging_infrastructure.LOCATIONS,
    power_list=config.charging_infrastructure.CHARGING_STATION_POWER,
    capacity_list=config.charging_infrastructure.CHARGING_STATION_CAPACITY,
    queue_size=config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE,
    reset=True,
)

#### End Charging Infrastructure Configuration #####


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Demand Data (once).                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

p = os.path.normpath(config.path.PATH_TRIP_DEMAND)
di = DemandImporter(
    spatial_resolution=config.world.SPATIAL_RESOLUTION,
    temporal_resolution=config.world.TEMPORAL_RESOLUTION,
    daily_resolution=config.world.DAILY_RESOLUTION,
    city=config.world.CITY,
)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(
    f"hex_{config.world.SPATIAL_RESOLUTION_VALUE}"
).index.tolist()
dmi = DistanceMatrixImporter(
    hexagons,
    config.world.SPATIAL_RESOLUTION_VALUE,
    os.path.normpath(os.path.join(".", "data", "infrastructure")),
    config.world.CITY,
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
    config.ride_hailing_global.N_RIDE_HAILING_CARS,
    config.ride_hailing_global.N_AUTONOMOUS_CARS,
]

# Get the supply probability from supply file
supply_prob = pd.read_csv(os.path.normpath(config.path.PATH_VEHICLE_SUPPLY))

ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=config.ride_hailing_global.N_RIDE_HAILING_CARS,
    n_AVs=config.ride_hailing_global.N_AUTONOMOUS_CARS,
)
ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_0
)


ride_hailing_fleet_config_1 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=config.ride_hailing_global.N_RIDE_HAILING_CARS,
    n_AVs=config.ride_hailing_global.N_AUTONOMOUS_CARS,
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
allow_queue = sum(config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE) > 0

ridehailing_operations_0 = RideHailingBaseChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=config.ride_hailing_operators[0].OPERATIONS_START,
    operation_duration=config.ride_hailing_operators[0].OPERATIONS_DURATION,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ride_hailing_operators[0].RECHARGE_THRESHOLD,
    allow_queue=allow_queue,
)

ridehailing_operations_1 = RideHailingBaseChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=config.ride_hailing_operators[0].OPERATIONS_START,
    operation_duration=config.ride_hailing_operators[0].OPERATIONS_DURATION,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ride_hailing_operators[0].RECHARGE_THRESHOLD,
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
    modifiers=[os.path.normpath(path) for path in config.path.PATH_DEMAND_MODIFIERS],
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
def run_simulation(end_time, env=env):  # noqa: ANN001, ANN201
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


env = simpy.Environment(config.experiment_management.START_TIME)
run_simulation(end_time=config.experiment_management.END_TIME)
