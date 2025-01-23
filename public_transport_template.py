##Imports
# Standard library imports
import logging
import os
import sys
from configparser import ConfigParser
from pathlib import Path

# Third-party library imports
import pandas as pd
import simpy

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    BusConfig,
    Configuration,
    TransitOperatorConfig,
    UserConfig,
)
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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Log Level
log_level = parser.get("SETTINGS", "log_level")

# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
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
cf = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf)

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

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand").format(city=city)
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Input Files (Infrastructure)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")

# Probability of the population to be price sensitive
price_sensitive_pop_prob = parser.get(
    "SHARED_VEHICLE_OPERATOR", "population_probabilities"
).split(",")
price_sensitive_pop_prob = [float(x) for x in price_sensitive_pop_prob]

# Operator Config
transit_planning_lookahead = parser.getint("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD")
transit_max_busses = parser.getint("TRANSIT_OPERATOR", "MAX_BUSSES")

# Create transit operator configuration
transit_operator_config = TransitOperatorConfig(
    transit_planning_lookahead, transit_max_busses
)

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# User configuration
max_waiting_time = parser.get("USER", "TRANSIT_MAX_WAIT")
spatial_strategy = parser.get("USER", "SPATIAL_STRATEGY")
walking_speed = parser.getfloat("USER", "WALKING_SPEED_KPH")

# Create user configuration
user_config = UserConfig(spatial_strategy, max_waiting_time, walking_speed)

# Bus configuration
bus_seats = parser.getint("BUS", "SEATS")
bus_velocity = parser.getfloat("BUS", "VELOCITY")
bus_config = BusConfig(bus_velocity, bus_seats)

# Register all configurations
global_config.add_user_config(user_config)
global_config.add_bus_config(bus_config)
global_config.add_transit_operator_config(transit_operator_config)
# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply").format(city=city)
# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=start_time)

# Population Type
population_factory = PopulationFactory(price_sensitive_pop_prob, seed)

# Load Spatial Environment
load_environment(city)

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
GeodesicEnvironment.getInstance().reset_random_generator(seed)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Output Configuration                    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Output Config
output_folder = parser.get("OUTPUT", "output_folder")
transaction_file = parser.get("OUTPUT", "transaction_file")

global_config.set_output_path(output_folder)
global_config.set_transaction_file(transaction_file)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

tracking = Tracking.init(env)

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
population_factory = PopulationFactory(price_sensitive_pop_prob, seed)

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
    env, demand_profile, di, world, demand_modifier_paths, seed, mode="public_transport"
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

    run_simulation(end_time=1440)
