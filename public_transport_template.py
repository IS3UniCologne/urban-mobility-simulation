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
    Configuration,
    RideHailingOperatorConfig,
    RideHailingVehicleConfig,
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
from simulation.operator.fleet_factory import (
    generate_mixed_ride_hailing_fleet,
    generate_ridehailing_fleet_config,
)
from simulation.operator.operations_management.operations_public_transport import (
    OperationsPublicTransport,
)
from simulation.operator.public_transit_operator_refactor import PublicTransitOperator
from simulation.operator.public_transport_allocation_engine import (
    PublicTransportAllocationEngine,
)
from simulation.operator.public_transport_search_engine import (
    PublicTransportSearchEngine,
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
transit_planning_lookahead = parser.get("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD")
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
walking_speed_mpm = parser.get("USER", "WALKING_SPEED_MPM")

# Create user configuration
user_config = UserConfig(spatial_strategy, max_waiting_time, walking_speed_mpm)

# Register all configurations
global_config.add_user_config(user_config)
global_config.add_transit_operator_config(transit_operator_config)
# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply").format(city=city)
# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)

# Initialize config for different vehicle types
for idx, vehicle_type in enumerate(["AUTONOMOUS_CAR", "RIDEHAILING_CAR"]):
    vehicle_type_classes = ["AutonomousCar", "RideHailingCar"]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC")
    charging_cost_per_kwh = parser.getfloat(vehicle_type, "CHARGING_COST_PER_KWH")
    cost_per_km = parser.getfloat(vehicle_type, "COST_PER_KM")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")
    EV_relative_energy_consumption = parser.getfloat(
        vehicle_type, "EV_RELATIVE_ENERGY_CONSUMPTION"
    )

    rvc = RideHailingVehicleConfig(
        price_per_min,
        max_state_of_charge,
        energy_consumption,
        velocity,
        max_available_seats,
        initial_SoC,
        charging_cost_per_kwh,
        cost_per_km,
        daily_total_cost,
        EV_relative_energy_consumption,
    )
    global_config.add_ridehailing_vehicle_config(vehicle_type_classes[idx], rvc)

# Number of ridehailing cars in the fleet
n_ridehailing_cars = parser.getint("RIDE_HAILING", "N_RIDEHAILING_CARS")
# Number of autonomous cars in the fleet
n_autonomous_cars = parser.getint("RIDE_HAILING", "N_AUTONOMOUS_CARS")
# Not sure what this is for
allocation = parser.get("RIDE_HAILING", "ALLOCATION")
# A score that represents how much users trust autonomous vehicles. Not relevant for every simulation
AV_trust = parser.get("MODE_CHOICE_MODEL", "AV_trust").split(",")
AV_trust = [float(x) for x in AV_trust]
AV_price_reduction = parser.getfloat("RIDE_HAILING", "AV_PRICE_REDUCTION")
discount_rate = parser.getint("RIDE_HAILING", "DISCOUNT_RATE")

AV_penetration = parser.getfloat("SUPPLY", "AV_penetration")
EV_penetration = parser.getfloat("SUPPLY", "EV_penetration")
# Drivers share of the revenue made with each ride
driver_payment_share = parser.getfloat("RIDE_HAILING", "DRIVER_PAYMENT_SHARE")
price_params = parser.get("RIDE_HAILING", "PRICE_PARAMS")
price_params = price_params.split(",")
price_params = [float(x) * (1 - discount_rate) for x in price_params]
# Maximumn pickuo distance that is ok for the users
distance_threshold = parser.getfloat("RIDE_HAILING", "MAX_PICKUP_DISTANCE")
global_config.add_distance_threshold_to_user(distance_threshold)
# Vehicles whose state of charge is below the threshold value are to be charged
recharge_threshold = parser.get("RIDE_HAILING_OPERATOR", "RECHARGE_THRESHOLD").split(
    ","
)
recharge_threshold = [float(x) / 100 for x in recharge_threshold]

operations_start = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint(
    "RIDE_HAILING_OPERATOR", "VEHICLE_RELOCATION_VELOCITY"
)

# Read drivers availability distribution
drivers_availability = parser.get("SUPPLY", "RH_availability").split(",")
drivers_availability = [
    round(float(x) * n_ridehailing_cars * (1 - AV_penetration))
    for x in drivers_availability
]
available_modes = parser.get("RIDE_HAILING", "AVAILABLE_VEHICLE_MODES_RIDEHAILING")
available_modes = available_modes.split(",")
available_modes_supply = [n_ridehailing_cars, n_autonomous_cars]

rhoc = RideHailingOperatorConfig(
    recharge_threshold=recharge_threshold,
    operations_start=operations_start,
    operations_duration=operations_duration,
    vehicle_relocation_velocity=vehicle_relocation_velocity,
    available_modes=available_modes,
    available_modes_supply=available_modes_supply,
    n_autonomous_cars=n_autonomous_cars,
    n_ridehailing_cars=n_ridehailing_cars,
    allocation=allocation,
)

global_config.add_ridehailing_operator_config(rhoc)
global_config.add_tech_penetration(EV_penetration, AV_penetration)
global_config.add_AV_trust(AV_trust)
global_config.add_driver_availability_vector(drivers_availability)
global_config.add_ride_hailing_info(
    driver_payment_share, AV_price_reduction, price_params
)


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
# Operations Module
operations = OperationsPublicTransport(env, timetable)

fleet_config = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=0,
    n_AVs=0,
    allocation_method="historical",
    allocation=allocation,
)
fleet = generate_mixed_ride_hailing_fleet(env, fleet_config)

# Operator Modules
search_engine = PublicTransportSearchEngine(env)

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

search_engine.register_fleet(fleet)

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


sum_iterations = 1 # throws Exception if value > 1: ValueError until (1440) must be greater than the current simulation time
for i in range(sum_iterations): 
    env = simpy.Environment(initial_time=start_time)

    run_simulation(end_time=end_time)
