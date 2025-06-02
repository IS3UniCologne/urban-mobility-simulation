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

# Live Visualization
import threading
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# Import configurations and extra logging filters
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
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=config.experiment_management.START_TIME)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
logger.addFilter(cf)

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
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timetable = Timetable(os.path.normpath(config.path.PATH_TRANSIT_TIMETABLE))
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
    config.population.TRANSIT_POPULATION_PROBABILITIES
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
    modifiers=[os.path.normpath(path) for path in config.path.PATH_DEMAND_MODIFIERS],
    mode="public_transport",
)

# env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Live Visualization                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timestamp = []
y1 = []
y2 = []

# callback function to get data from world
def get_n_users():
    timestamp.append(env.now)
    y1.append(len(world._users))
    y2.append(len(world._user_processes))

    return timestamp, y1, y2


def animate(i, callback):
    if callback is not None:
        timestamp, n_users, n_active_users = callback()

        # clear whole figure
        plt.clf()

        # plot 1
        plt.subplot(3, 1, 1)
        plt.plot(timestamp,n_users, n_active_users)
        plt.title("n users in world")
        plt.legend(["n_users", "n_user_processes"], loc="upper right")

        # plot 2
        plt.subplot(3, 1, 2)
        plt.plot(timestamp,n_users)
        plt.title("n users in world")

        # plot 3
        plt.subplot(3, 1, 3)
        plt.plot(timestamp,n_users)
        plt.title("n users in world")

        plt.tight_layout()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run the Simulation                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# env.process(operator._run())

# logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

# env.run(until=end_time)

# logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})


def run_simulation(end_time, env=env):  # noqa: ANN001, ANN201
    # Before a new simulation run, reset everything
    User.user_id = 0
    DemandFactory.counter = 0
    Vehicle.vehicle_id = 0
    PublicTransitVehicle.public_transit_vehicle_id = 0
    Bus.bus_id = 0

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

    transactions = operator.transaction_df
    transactions_dir = os.path.normpath(os.path.join("data", "output"))
    transactions.to_csv(os.path.join(transactions_dir, "transactions.csv"), index=False)


sum_iterations = 1  # throws Exception if value > 1: ValueError until (1440) must be greater than the current simulation time
for i in range(sum_iterations):
    # env = simpy.Environment(initial_time=600)

    urban_mobility_simulation = threading.Thread(target=run_simulation, args=(1440,))

    urban_mobility_simulation.start()

    ani = FuncAnimation(
        plt.gcf(),
        animate,
        frames=100,
        interval=1000,
        cache_frame_data=False,
        fargs=(get_n_users,)
    )
    plt.show()

    run_simulation(end_time=config.experiment_management.END_TIME)
