##Imports
# Standard library imports
import logging
import os
import sys
from configparser import ConfigParser
from pathlib import Path

import numpy as np
import pandas as pd

# Third-party library imports
import simpy

import utils

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    Configuration,
    ModeChoiceConfig,
    PopulationConfig,
    RideHailingOperatorConfig,
    RideHailingVehicleConfig,
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
from simulation.operator.operations_management.ridehailing_charging_operations import (
    RideHailingChargingOperations,
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
from utils import load_environment

# Change working directory to path of this file
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

### Input Files
# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand").format(city=city)
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply").format(city=city)
# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)


pop_prob_ridehailing = parser.get("RIDE_HAILING", "population_probabilities").split(",")
pop_prob_ridehailing = [float(x) for x in pop_prob_ridehailing]

mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")

# Initialize the mode choice config
mc = ModeChoiceConfig(
    mode_choice_strategy, mode_choice_sub_boundary, mode_choice_model_path
)

# Load the config to the global config
global_config.add_mode_choice_config(mc)


if mode_choice_strategy == "substitution":
    vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
        ["AutonomousCar", "RideHailingCar"]
    )  ## Needs to be modified depending on the modus

else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####

#### Not sure if this part is necessary #####
MoD_interval_reduction = 0  # By choice
global_config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# RideHailing Fleet Configuration         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

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
vehicle_relocation_velocity = parser.getfloat(
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

###### End RideHailing Fleet Configuration ######

#### Population Configuration ####

population_probabilities = parser.get("POPULATION", "population_probabilities").split(
    ","
)
population_probabilities = [float(x) for x in population_probabilities]

type_paths = parser.get("POPULATION", "type_paths")

pc = PopulationConfig(population_probabilities, type_paths)

global_config.add_population_config(pc)

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
population_factory = PopulationFactory(pop_prob_ridehailing, seed)

# Load Spatial Environment and the environment files
load_environment(city)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Charging Infrastructure                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

number_of_charging_locations = parser.getint(
    "CHARGING_INFRASTRUCTURE", "NUMBER_OF_CHARGING_STATIONS"
)
# Locations are defined as hexagons (regions) in the city
charging_station_locations = utils.parse_multiline_list(
    "CHARGING_INFRASTRUCTURE", "LOCATIONS", delimiter=","
)
charging_station_locations = charging_station_locations[:number_of_charging_locations]

charging_station_power = utils.parse_multiline_list(
    "CHARGING_INFRASTRUCTURE", "CHARGING_STATION_POWER", delimiter=",", cast=float
)
if len(charging_station_power) == 1:
    charging_station_power = list(
        np.full(number_of_charging_locations, charging_station_power[0])
    )

# Capacity is the number of charging stations in the charging hub (or plugs at a station)
charging_station_capacity = utils.parse_multiline_list(
    "CHARGING_INFRASTRUCTURE", "CHARGING_STATION_CAPACITY", delimiter=",", cast=int
)
if len(charging_station_capacity) == 1:
    charging_station_capacity = list(
        np.full(number_of_charging_locations, charging_station_capacity[0])
    )

number_of_charging_stations = parser.getint(
    "CHARGING_INFRASTRUCTURE", "NUMBER_OF_CHARGING_STATIONS"
)
charging_location_list = utils.parse_multiline_list(
    "CHARGING_INFRASTRUCTURE", "LOCATIONS", delimiter=","
)[:number_of_charging_locations]
if isinstance(charging_station_power, list):
    charging_station_power_list = charging_station_power
else:
    charging_station_power_list = list(
        np.full(len(charging_location_list), charging_station_power)
    )
if isinstance(charging_station_capacity, list):
    charging_station_capacity_list = charging_station_capacity
else:
    charging_station_capacity_list = list(
        np.full(len(charging_location_list), charging_station_capacity)
    )
sic = ChargingInfrastructureConfig(
    charging_location_list, charging_station_power_list, charging_station_capacity_list
)
global_config.add_charging_infrastructure_config(sic)
charging_infrastructure = ChargingInfrastructure(
    env,
    charging_location_list,
    charging_station_power_list,
    charging_station_capacity_list,
    reset=True,
)

#### End Charging Infrastructure Configuration #####

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Output Configuration                    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

store_results = parser.getboolean("OUTPUT", "persist_results")
store_results = parser.getboolean("OUTPUT", "persist_results")
output_folder = parser.get("OUTPUT", "output_folder")
transaction_file = parser.get("OUTPUT", "transaction_file")
fleet_state_file = parser.get("OUTPUT", "fleet_state_file")

global_config.set_store_results(store_results)
global_config.set_output_path(output_folder)
global_config.set_transaction_file(transaction_file)
global_config.set_fleet_state_file(fleet_state_file)

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

GeodesicEnvironment.getInstance().reset_random_generator(4711)

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
available_vehicle_modes_supply_ride_hailing = [n_ridehailing_cars, n_autonomous_cars]

ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=n_ridehailing_cars,
    n_AVs=n_autonomous_cars,
    allocation_method="historical",
    allocation=allocation,
)
ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_0
)

ride_hailing_fleet_config_1 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=n_ridehailing_cars,
    n_AVs=n_autonomous_cars,
    allocation_method="historical",
    allocation=allocation,
)
ride_hailing_fleet_1 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_1
)

# Add the fleet to the search engine
search_engine["ride_hailing_0"].register_fleet(ride_hailing_fleet_0)
search_engine["ride_hailing_1"].register_fleet(ride_hailing_fleet_1)

# Initialize fleet operations

ridehailing_operations_0 = RideHailingChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=global_config.ridehailing_operator_config.operations_start,
    operation_duration=global_config.ridehailing_operator_config.operations_duration,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=global_config.ridehailing_operator_config.recharge_threshold,
)

ridehailing_operations_1 = RideHailingChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=global_config.ridehailing_operator_config.operations_start,
    operation_duration=global_config.ridehailing_operator_config.operations_duration,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=global_config.ridehailing_operator_config.recharge_threshold,
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
    env, demand_profile, di, world, [], seed, mode="ride_hailing"
)
env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

env.run(until=end_time)

logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})
