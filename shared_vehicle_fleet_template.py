##### This is a template for a sharedvehicle fleet consisting of shared cars, schared scooters and shared kickscooters. Shared bikes are not yet added ########

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
from simulation.helper.configuration.enums import VehicleMode
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)

# Custom module imports
# Import metrics
# Import operator related modules
from simulation.metrics.metrics_factory import MetricsFactory
from simulation.operator.fleet_factory import (
    generate_fleet_config,
    generate_mixed_fleet,
)
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.vehicle.shared_bike import SharedBike

# Import vehicle types and vehicle choice options
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle.shared_vehicle import SharedVehicle
from simulation.vehicle_choice_model.distance_based_shared_vehicle_choice_behavior import (
    DistanceBasedSharedVehicleVehicleChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking

# Custom module imports
from utils import load_geodesic_environment

pd.set_option("display.max_columns", None)

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
shutil.copy(sys.argv[1], f"data/output/configs/{output_timestamp}.toml")

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
# Shared Vehicle Fleet Configuration      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: SharedScooters and SharedKickScooters do not have an initial state of charge. They start with the max state of charge.

# Vehicle Choice Model
if (
    config.mode_choice_model.MODE_CHOICE_STRATEGY
    == ModeChoiceStrategy.SUBSTITUTION_AWARE
):
    vehicle_choice_model = DistanceBasedSharedVehicleVehicleChoiceBehavior(
        os.path.normpath(config.path.PATH_TO_MODE_CHOICE_MODEL),
        config.mode_choice_model.SUBSTITUTION_BOUNDARY,
        config.shared_vehicle_global.AVAILABLE_VEHICLE_MODES,
    )
else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=config.experiment_management.START_TIME)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
logger.addFilter(cf)


# Population Type
population_factory = PopulationFactory(
    config.population.SHARED_VEHICLE_POPULATION_PROBABILITIES
)

# Load Spatial Environment and the environment files
load_geodesic_environment()

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

SharedBike.shared_bike_id = 0
SharedVehicle.shared_vehicle_id = 0
SharedKickScooter.shared_kick_scooter_id = 0
SharedScooter.shared_scooter_id = 0
SharedBike.shared_bike_id = 0
User.user_id = 0
DemandFactory.counter = 0


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

tracking = Tracking.init(env)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules.               #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Search Engine finds transportation alternatives for users and manages payment processes
search_engine = SharedVehicleSearchEngine(env)

# Vehicle Assignment Engine assigns users to vehicles and notifies them about the pickup position
vehicle_assignment_engine = SharedVehicleAllocationEngine(env)

# Get the supply probability from supply file
supply_prob = pd.read_csv(os.path.normpath(config.path.PATH_VEHICLE_SUPPLY))

# Configure and generate / spawn shared fleet vehicles
shared_vehicle_fleet_config = generate_fleet_config(
    supply_prob,
    n_cars=config.shared_vehicle_operators[0].N_VEHICLES[VehicleMode.Car],
    n_scooter=config.shared_vehicle_operators[0].N_VEHICLES[VehicleMode.Scooter],
    n_kick_scooter=config.shared_vehicle_operators[0].N_VEHICLES[
        VehicleMode.KickScooter
    ],
    n_bikes=config.shared_vehicle_operators[0].N_VEHICLES[VehicleMode.Bike],
)
mixed_fleet = generate_mixed_fleet(env, shared_vehicle_fleet_config)

# Add the fleet to the search engine
search_engine.register_fleet(mixed_fleet)


operations = IntegratedSharedMobilityOperations(
    env=env,
    time_between_operations=config.shared_vehicle_operators[0].OPERATIONS_START,
    operation_duration=config.shared_vehicle_operators[0].OPERATIONS_DURATION,
    distance_matrix=distance_matrix,
    ordered_available_vehicle_modes=config.shared_vehicle_operators[
        0
    ].AVAILABLE_VEHICLE_MODES,
    ordered_max_vehicle_supply=config.shared_vehicle_operators[
        0
    ].AVAILABLE_MODES_SUPPLY,
    state_of_charge_threshold=config.shared_vehicle_operators[0].RECHARGE_THRESHOLD,
    base_regions=config.shared_vehicle_operators[0].BASE_REGIONS,
    base_capacity=config.shared_vehicle_operators[0].BASE_CAPACITY,
)

# Init operator
operator = SharedMobilityOperator(
    env=env,
    fleet=mixed_fleet,
    charging_infrastructure=None,
    operations=operations,
    search_engine=search_engine,
    allocation_engine=vehicle_assignment_engine,
    number_service_workers=config.shared_vehicle_operators[0].NUMBER_OF_SERVICE_WORKERS,
)

# Initialize World
world = World.init(
    env=env,
    search_engine=search_engine,
    payment_engine=operator,
    vehicle_assignment_engine=vehicle_assignment_engine,
    vehicle_choice_behavior=vehicle_choice_model,
    population_factory=population_factory,
    charging_infrastructure=None,
    reset=True,
)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Spawn Demand Processes.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: we need to have a look at https://github.com/IS3UniCologne/urban-mobility-simulation/issues/32
demand_factory = DemandFactory(
    env,
    demand_profile,
    di,
    world,
    modifiers=[os.path.normpath(path) for path in config.path.PATH_DEMAND_MODIFIERS],
    mode="shared_vehicle",
)


def get_cost_per_vehicle_km():
    res = {}

    for key, value in config.shared_vehicles.items():
        res[key.name] = value.COST_PER_KM

    return res


def get_co2_per_vehicle_km():
    res = {}

    for key, value in config.shared_vehicles.items():
        res[key.name] = value.KG_CO2_PER_KM

    return res


# For multiple simulation runs
def run_simulation(end_time, env=env):
    # Before a new simulation run, reset everything
    User.user_id = 0
    DemandFactory.counter = 0
    SharedKickScooter.shared_kick_scooter_id = 0
    SharedScooter.shared_scooter_id = 0
    DemandFactory.counter = 0

    # Inject Simulation Environment to Logger (such that we can log the env time)
    cf = SimulationContextFilter(filter_name="add_env", extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    env.process(operations.execute())

    # Use only if the configuration parameters stay unchanged to avoid reloading everytime. Reload demand factory if the demand profile is different between consecutive runs
    demand_factory.reset()

    env.process(demand_factory.generate_demand())

    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    # Run the simulation until end time
    env.run(until=end_time)

    logging.warning("Ending Simulation.", extra={"clazz": "main", "oid": ""})

    transactions = operator.get_transactions()
    if transactions.size > 0:
        transactions_dir = os.path.normpath(os.path.join("data", "output"))
        transactions.to_csv(
            os.path.join(transactions_dir, "transactions.csv"), index=False
        )

        metrics_factory = MetricsFactory(transactions)

        num_vehicles = {
            "SharedBike": config.shared_vehicle_global.VEHICLES[VehicleMode.Bike],
            "SharedCar": config.shared_vehicle_global.VEHICLES[VehicleMode.Car],
            "SharedKickScooter": config.shared_vehicle_global.VEHICLES[
                VehicleMode.KickScooter
            ],
            "SharedScooter": config.shared_vehicle_global.VEHICLES[VehicleMode.Scooter],
        }

        metrics_factory.print_simulation_summary(
            num_vehicles, get_cost_per_vehicle_km(), get_co2_per_vehicle_km()
        )


run_simulation(end_time=config.experiment_management.END_TIME)
