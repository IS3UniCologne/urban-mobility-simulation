##### This is a template for a sharedvehicle fleet consisting of shared cars, schared scooters and shared kickscooters. Shared bikes are not yet added ########

##Imports
# Standard library imports
import logging
import os
import sys
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
from simulation.vehicle.shared_car import SharedCar
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

# Initialize an empty Configuration object
config = Configuration.instance()

# Initialize ConfigReader with the configuration file and the Configuration object
config_reader = ConfigReader(sys.argv[1])
config_reader.load_config()

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
# Shared Vehicle Fleet Configuration      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: SharedScooters and SharedKickScooters do not have an initial state of charge. They start with the max state of charge.

# Vehicle Choice Model
if (
    config.get_mode_choice_config().mode_choice_strategy
    == ModeChoiceStrategy.SUBSTITUTION_AWARE
):
    vehicle_choice_model = DistanceBasedSharedVehicleVehicleChoiceBehavior(
        config.get_mode_choice_config().path_to_model,
        config.get_mode_choice_config().substitution_boundary,
        config.shared_vehicle_operator_config.available_modes,
    )
else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

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

# Population Type
population_factory = PopulationFactory(
    config.shared_vehicle_population_probabilities, config.seed
)

# Load Spatial Environment and the environment files
load_geodesic_environment()

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

GeodesicEnvironment.getInstance().reset_random_generator(4711)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Reset counters and random number        #
# generators before each run              #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

SharedBike.shared_bike_id = 0
SharedVehicle.shared_vehicle_id = 0
SharedCar.car_id = 0
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
supply_prob = pd.read_csv(config.vehicle_supply_file)

# Configure and generate / spawn shared fleet vehicles
shared_vehicle_fleet_config = generate_fleet_config(
    supply_prob,
    n_cars=config.shared_vehicle_operator_config.n_cars,
    n_scooter=config._shared_vehicle_operator_config.n_scooters,
    n_kick_scooter=config.shared_vehicle_operator_config.n_kickscooters,
    n_bikes=config.shared_vehicle_operator_config.n_bikes,
)
mixed_fleet = generate_mixed_fleet(env, shared_vehicle_fleet_config)

# Add the fleet to the search engine
search_engine.register_fleet(mixed_fleet)


operations = IntegratedSharedMobilityOperations(
    env=env,
    time_between_operations=config.shared_vehicle_operator_config.operations_start,
    operation_duration=config.shared_vehicle_operator_config.operations_duration,
    distance_matrix=distance_matrix,
    ordered_available_vehicle_modes=config.shared_vehicle_operator_config.available_modes,
    ordered_max_vehicle_supply=config.shared_vehicle_operator_config.available_modes_supply,
    state_of_charge_threshold=config.shared_vehicle_operator_config.recharge_threshold,
    base_regions=config.shared_vehicle_operator_config.base_regions,
    base_capacity=config.shared_vehicle_operator_config.base_capacity,
)

# Init operator
operator = SharedMobilityOperator(
    env=env,
    fleet=mixed_fleet,
    charging_infrastructure=None,
    operations=operations,
    search_engine=search_engine,
    allocation_engine=vehicle_assignment_engine,
    number_service_workers=config.shared_vehicle_operator_config.number_of_service_workers,
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
    config.demand_modifier_files,
    config.seed,
    mode="shared_vehicle",
)


# For multiple simulation runs
def run_simulation(end_time, seed=4711, env=env):
    # Before a new simulation run, reset everything
    User.user_id = 0
    DemandFactory.counter = 0
    SharedCar.car_id = 0
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
        transactions.to_csv("data/output/transactions.csv", index=False)

        metrics_factory = MetricsFactory(transactions)

        num_vehicles = {
            "SharedBike": config.shared_vehicle_operator_config.n_bikes,
            "SharedCar": config.shared_vehicle_operator_config.n_cars,
            "SharedKickScooter": config.shared_vehicle_operator_config.n_kickscooters,
            "SharedScooter": config.shared_vehicle_operator_config.n_scooters,
        }

        metrics_factory.print_simulation_summary(
            num_vehicles,
            config.get_cost_per_vehicle_km(),
            config.get_co2_per_vehicle_km(),
        )


run_simulation(end_time=config.end_time)
