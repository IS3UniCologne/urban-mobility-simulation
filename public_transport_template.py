##Imports
# Standard library imports
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Third-party library imports
import simpy

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# Import configurations and extra logging filters
from simulation.helper.configuration.config_reader import ConfigReader
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.infrastructure.helper.timetable import Timetable

# Import operator related modules
from simulation.operator.operations_management.operations_public_transport import (
    OperationsPublicTransport,
)
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.operator.public_transport_allocation_engine import (
    PublicTransportAllocationEngine,
)
from simulation.operator.public_transport_search_engine import (
    PublicTransportSearchEngine,
)
from simulation.operator.public_transport_vehicle_fleet import (
    PublicTransportVehicleFleet,
)
from simulation.vehicle.public_transit_bus import Bus

# Import vehicle types and vehicle choice options
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from simulation.vehicle.vehicle import Vehicle
from simulation.vehicle_choice_model.public_transit_vehicle_choice_behavior import (
    PublicTransitVehicleChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory

# must come before DemandFactory, otherwise circular imports
from simulation.world.world import World
from tracking.tracking import Tracking

# Custom module imports
from utils import load_geodesic_environment

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Configuration from ini file.       #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Change working directory to path of main.py
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
cf_init = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf_init)


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Basic Configuration                     #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=config.start_time)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
edf = ExtraDefaultFilter(filter_name="add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)

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
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timetable = Timetable(config.get_infrastructure_config().path_transit_timetable)
timetable.import_timetable()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Reset counters and random number        #
# generators before each run              #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

Vehicle.vehicle_id = 0
PublicTransitVehicle.public_transit_vehicle_id = 0
Bus.bus_id = 0
User.user_id = 0
DemandFactory.counter = 0
GeodesicEnvironment.getInstance().reset_random_generator(config.seed)


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

fleet = PublicTransportVehicleFleet(env)

# Operator Modules
search_engine = PublicTransportSearchEngine(env, fleet)

# Operations Module
operations = OperationsPublicTransport(env, timetable, fleet)

vehicle_assignment_engine = PublicTransportAllocationEngine(env)

# Operator Module
operator = PublicTransitOperator(
    env,
    fleet=fleet,
    charging_infrastructure=None,
    operations=operations,
    search_engine=search_engine,
    allocation_engine=vehicle_assignment_engine,
)

payment_engine = operator

# Vehicle Choice Model
vehicle_choice_model = PublicTransitVehicleChoiceBehavior(["Bus"])

# Population Type
population_factory = PopulationFactory(
    config.transit_population_probabilities, config.seed
)

# World --> Charging Infrastructure is irrelevant for the public operator so this is set to None
world = World.init(
    env,
    search_engine,
    payment_engine,
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
    config.demand_modifier_files,
    config.seed,
    mode="public_transport",
)

# env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run the Simulation                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# env.process(operator._run())

# logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

# env.run(until=end_time)

# logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})


def run_simulation(end_time, seed=4711, env=env):
    # Before a new simulation run, reset everything
    User.user_id = 0
    DemandFactory.counter = 0
    Vehicle.vehicle_id = 0
    PublicTransitVehicle.public_transit_vehicle_id = 0
    Bus.bus_id = 0
    GeodesicEnvironment.getInstance().reset_random_generator(seed)

    # Inject Simulation Environment to Logger (such that we can log the env time)
    cf = SimulationContextFilter(filter_name="add_env", extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    # Use only if the configuration parameters stay unchanged to avoid reloading everytime. Reload demand factory if the demand profile is different between consecutive runs
    demand_factory.reset()

    env.process(demand_factory.generate_demand())

    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    # Run simulation

    env.run(until=end_time)

    logging.warning("Ending Simulation.", extra={"clazz": "main", "oid": ""})

    transactions = operator.get_transactions()
    transactions.to_csv("data/output/transactions.csv", index=False)


sum_iterations = 1  # throws Exception if value > 1: ValueError until (1440) must be greater than the current simulation time
for i in range(sum_iterations):
    env = simpy.Environment(initial_time=600)

    run_simulation(end_time=config.end_time, seed=config.seed)
