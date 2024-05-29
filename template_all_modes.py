# ALARM!: This template is not able to fulfil the purpose of running several modes
# simultaneously, since the user refactoring will have to enable several modes at the same time.
# This can then be used as a starting point


### This is the template for a simulation with a ridehailing and shared mobility fleet. #####

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
    SharedVehicleConfig,
    SharedVehicleOperatorConfig,
    TransitOperatorConfig,
    UserConfig,
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
from simulation.infrastructure.helper.timetable import Timetable

# Import operator related modules
from simulation.operator.fleet_factory import (
    generate_fleet_config,
    generate_mixed_fleet,
    generate_mixed_ride_hailing_fleet,
    generate_ridehailing_fleet_config,
)
from simulation.operator.operations_management.operations import Operations
from simulation.operator.operations_management.operations_ridehailing import (
    OperationsRidehailing,
)
from simulation.operator.operations_management.rebalancing_scheduler_ridehailing import (
    RebalancingSchedulerRidehailing,
)
from simulation.operator.operations_management.relocation_scheduler import (
    RelocationScheduler,
)
from simulation.operator.operations_management.service_worker import ServiceWorker
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.operator.public_transit_operator import PublicTransitOperator
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter

# Import vehicle types and vehicle choice options
from simulation.vehicle.vehicle import Vehicle
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

# Input Files (Infrastructure)
transit_timetable_path = parser.get("INFRASTRUCTURE", "path_transit_timetable")

pop_prob_ridehailing = parser.get("RIDE_HAILING", "population_probabilities").split(",")
pop_prob_ridehailing = [float(x) for x in pop_prob_ridehailing]
pop_prob_sharedvehicle = parser.get(
    "SHARED_VEHICLE_OPERATOR", "population_probabilities"
).split(",")
pop_prob_sharedvehicle = [float(x) for x in pop_prob_sharedvehicle]
pop_prob_public = parser.get("TRANSIT_OPERATOR", "population_probabilities").split(",")
pop_prob_public = [float(x) for x in pop_prob_public]

mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")

# Initialize the mode choice config
mc = ModeChoiceConfig(
    mode_choice_strategy, mode_choice_sub_boundary, mode_choice_model_path
)

# Load the config to the global config
global_config.add_mode_choice_config(mc)


# TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/51
if mode_choice_strategy == "substitution":
    # For now modify this depending on the modus
    # vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
    #     ["SharedScooter", "SharedKickScooter", "SharedCar", "SharedBike"]
    # )
    vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
        ["AutonomousCar", "RideHailingCar"]
    )
    # vehicle_choice_model = PublicTransitVehicleChoiceBehavior(['Bus'])

else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Bus / Operator Configuration            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Operator Config
transit_planning_lookahead = parser.get("TRANSIT_OPERATOR", "TRANSIT_LOOKAHEAD")
transit_max_busses = parser.getint("TRANSIT_OPERATOR", "MAX_BUSSES")

# User configuration
max_waiting_time = parser.get("USER", "TRANSIT_MAX_WAIT")
spatial_strategy = parser.get("USER", "SPATIAL_STRATEGY")

# Create transit operator configuration
transit_operator_config = TransitOperatorConfig(
    transit_planning_lookahead, transit_max_busses
)

# Create user configuration for public transport services
user_config = UserConfig(spatial_strategy, max_waiting_time)

# Register all configurations
global_config.add_user_config(user_config)
global_config.add_transit_operator_config(transit_operator_config)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Shared Vehicle Fleet Configuration      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: Implement SharedBikes --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/46
# TODO: SharedScooters and SharedKickScooters do not have an initial state of charge. They start with the max state of charge.
# Initialize config for different vehicle types
for idx, vehicle_type in enumerate(
    ["SHARED_CAR", "SHARED_SCOOTER", "SHARED_KICK_SCOOTER", "SHARED_BIKE"]
):
    vehicle_type_classes = [
        "SharedCar",
        "SharedScooter",
        "SharedKickScooter",
        "SharedBike",
    ]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    max_walking_distance = parser.getint(vehicle_type, "WALKING_DISTANCE")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")
    if vehicle_type == "SHARED_CAR":
        initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC")
    if vehicle_type != "SHARED_BIKE":
        EV_relative_energy_consumption = parser.getfloat(
            vehicle_type, "EV_RELATIVE_ENERGY_CONSUMPTION"
        )
        cost_per_km = parser.getfloat(vehicle_type, "COST_PER_KM")
        charging_cost_per_kWh = parser.getfloat(vehicle_type, "CHARGING_COSTS_PER_KM")

    vc = SharedVehicleConfig(
        price_per_min,
        max_state_of_charge,
        energy_consumption,
        velocity,
        max_available_seats,
        max_walking_distance,
        daily_total_cost,
        initial_SoC,
        EV_relative_energy_consumption,
        cost_per_km,
        charging_cost_per_kWh,
    )
    global_config.add_shared_vehicle_config(vehicle_type_classes[idx], vc)

# Needs to be modified depending on the mode
# Vehicles whose state of charge is below the threshold value are to be charged
recharge_threshold = (
    parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD") / 100
)
charging_station_power = parser.getfloat(
    "SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER"
)  # Think about moving this to charging infrastructure
# Service workers relocate the vehicles and bring them to charging stations
number_of_service_workers = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER"
)
# Base regions are city parts in which these service workers operate
number_of_base_regions = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_BASE_REGIONS"
)
# Base regions are defined as hexagons in the city
base_regions = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
base_regions = base_regions.split(",")[:number_of_base_regions]
# Base capacity is the number of charging stations in the charging hub
base_capacity = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
operations_start = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint(
    "SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY"
)

# Get number of each vehicle type to be spawned from configuration (Maybe move it to the shared vehicle operator?)
n_cars = parser.getint("EXPERIMENT_MANAGEMENT", "N_CARS")
n_kickscooters = parser.getint("EXPERIMENT_MANAGEMENT", "N_KICKSCOOTER")
n_bikes = parser.getint("EXPERIMENT_MANAGEMENT", "N_BIKES")
n_scooters = parser.getint("EXPERIMENT_MANAGEMENT", "N_SCOOTER")

available_modes = parser.get(
    "SHARED_VEHICLE_OPERATOR", "available_vehicle_modes_shared_vehicle"
)
available_modes = available_modes.split(",")
available_modes_supply = [n_cars, n_scooters, n_kickscooters, n_bikes]

# Initiliaze the shared fleet operator
svoc = SharedVehicleOperatorConfig(
    recharge_threshold,
    charging_station_power,
    number_of_service_workers,
    base_regions,
    base_capacity,
    operations_start,
    operations_duration,
    vehicle_relocation_velocity,
    available_modes,
    available_modes_supply,
    n_cars,
    n_scooters,
    n_kickscooters,
    n_bikes,
)
# Register all configurations
global_config.add_shared_vehicle_operator_config(svoc)

#### Not sure if this part is necessary #####
MoD_interval_reduction = 0  # By choice
global_config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction)

###### End Shared Vehicle Fleet Configuration ######

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
    charging_cost_per_km = parser.getfloat(vehicle_type, "CHARGING_COSTS_PER_KM")
    cost_per_km = parser.getfloat(vehicle_type, "COST_PER_KM")
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
        charging_cost_per_km,
        cost_per_km,
        EV_relative_energy_consumption,
    )
    global_config.add_ridehailing_vehicle_config(vehicle_type_classes[idx], rvc)

# Number of ridehailing cars in the fleet
n_ridehailing_cars = parser.getint("RIDE_HAILING", "n_ridehailing_cars")
# Number of autonomous cars in the fleet
n_autonomous_cars = parser.getint("RIDE_HAILING", "n_autonomous_cars")
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
# Maximumn pickup distance that is ok for the users
distance_threshold = parser.getfloat("RIDE_HAILING", "MAX_PICKUP_DISTANCE")
global_config.add_distance_threshold_to_user(distance_threshold)
# Vehicles whose state of charge is below the threshold value are to be charged
recharge_threshold = parser.get("RIDE_HAILING_OPERATOR", "RECHARGE_THRESHOLD").split(
    ","
)
recharge_threshold = [float(x) / 100 for x in recharge_threshold]

charging_station_power = parser.getfloat(
    "RIDE_HAILING_OPERATOR", "CHARGING_STATION_POWER"
)  ### Maybe this should belong to charging infrastructure?
# Service workers relocate the vehicles and bring them to charging stations
number_of_service_workers = parser.getint(
    "RIDE_HAILING_OPERATOR", "NUMBER_OF_SERVICE_WORKER"
)
# Base regions are city parts in which these service workers operate
number_of_base_regions = parser.getint(
    "RIDE_HAILING_OPERATOR", "NUMBER_OF_BASE_REGIONS"
)
# Base regions are defined as hexagons in the city
base_regions = parser.get("RIDE_HAILING_OPERATOR", "BASE_REGIONS")
base_regions = base_regions.split(",")[:number_of_base_regions]

# Base capacity is the number of charging stations in the charging hub
base_capacity = parser.getint("RIDE_HAILING_OPERATOR", "BASE_CAPACITY")
operations_start = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint(
    "RIDE_HAILING_OPERATOR", "VEHICLE_RELOCATION_VELOCITY"
)

# Read drivers availability distribution
drivers_availability = parser.get("SUPPLY", "RH_availability").split(",")
drivers_availability = [
    round(float(x) * n_cars * (1 - AV_penetration)) for x in drivers_availability
]
available_modes = parser.get("RIDE_HAILING", "available_vehicle_modes_ridehailing")
available_modes = available_modes.split(",")
available_modes_supply = [n_ridehailing_cars, n_autonomous_cars]

# Initiliaze the ridehailing operator
rhoc = RideHailingOperatorConfig(
    recharge_threshold,
    charging_station_power,
    number_of_service_workers,
    base_regions,
    base_capacity,
    operations_start,
    operations_duration,
    vehicle_relocation_velocity,
    available_modes,
    available_modes_supply,
    n_autonomous_cars,
    n_ridehailing_cars,
    allocation,
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

env = simpy.Environment(initial_time=start_time)

# Population Type
# TODO: Generate population for multiple modes at once --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/52
population_factory = PopulationFactory(pop_prob_ridehailing, seed)
# population_factory = PopulationFactory(pop_prob_public, seed)
# population_factory = PopulationFactory(pop_prob_sharedvehicle, seed)

# Load Spatial Environment together with the environment files
load_environment(city)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load GTFS Timetable (once).             #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timetable = Timetable(transit_timetable_path)
timetable.import_timetable()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Charging Infrastructure                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
# Doubled Code --> actually the same as number of base capacity
number_of_charging_stations = parser.getint(
    "Charging_Infrastructure", "NUMBER_OF_CHARGING_STATIONS"
)
charging_location_list = parser.get("Charging_Infrastructure", "BASE_REGIONS").split(
    ","
)[:number_of_charging_stations]

charging_power = parser.getint("Charging_Infrastructure", "CHARGING_POWER")
charging_capacity = parser.getint("Charging_Infrastructure", "CHARGING_CAPACITY")
charging_power_list = list(np.zeros(len(charging_location_list)) + charging_power)
charging_capacity_list = list(np.zeros(len(charging_location_list)) + charging_capacity)
sic = ChargingInfrastructureConfig(
    charging_location_list, charging_power_list, charging_capacity_list
)
charging_infrastructure = ChargingInfrastructure(
    env, charging_location_list, charging_power_list, charging_capacity_list, reset=True
)

global_config.add_charging_infrastructure_config(sic)

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
edf = ExtraDefaultFilter(filter_name="add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)


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
SharedCar.car_id = 0
SharedKickScooter.shared_kick_scooter_id = 0
SharedScooter.shared_scooter_id = 0
DemandFactory.counter = 0
Vehicle.vehicle_id = 0
PublicTransitVehicle.public_transit_vehicle_id = 0
Bus.bus_id = 0
# Add a counter for ridehailing car too

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

public_operator = PublicTransitOperator(env, timetable)

search_engine = {
    "ride_hailing_0": RideHailingSearchEngine(env),
    "shared_vehicle": SharedVehicleSearchEngine(env),
    "public_transport": public_operator,
}

# For RideHailing and Shared Fleet use the search engine as payment engine
payment_engine = search_engine

# For public operator the payment services are in the operator module itself
# payment_engine = search_engine["public_transport"]

vehicle_assignment_engine = {
    "ride_hailing_0": RideHailingAllocationEngine(env),
    "shared_vehicle": SharedVehicleAllocationEngine(env),
    "public_transport": public_operator,
}

# Configure and generate / spawn fleet vehicles
# Shared Vehicle Fleet
shared_vehicle_fleet_config = generate_fleet_config(
    supply_prob,
    n_cars=global_config.shared_vehicle_operator_config.n_cars,
    n_scooter=global_config._shared_vehicle_operator_config.n_scooters,
    n_kick_scooter=global_config.shared_vehicle_operator_config.n_kickscooters,
    n_bikes=global_config.shared_vehicle_operator_config.n_bikes,
)
mixed_fleet = generate_mixed_fleet(env, shared_vehicle_fleet_config)

# Ride Hailing Fleet
ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=global_config.ridehailing_operator_config.n_ridehailing_cars,
    n_AVs=global_config.ridehailing_operator_config.n_autonomous_cars,
    allocation_method="historical",
    allocation=global_config.ridehailing_operator_config.allocation,
)
ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_0
)

# Add the fleets to the search engine
search_engine["shared_vehicle"].register_fleet(mixed_fleet)
search_engine["ride_hailing_0"].register_fleet(ride_hailing_fleet_0)

# Initialize task queues for both fleets
task_queue_ridehailing = TaskQueue(env)
task_queue_shared_vehicle = TaskQueue(env)

# Spawn Service Workers for the Shared Fleet
for sw in range(global_config.shared_vehicle_operator_config.number_of_service_workers):
    env.process(ServiceWorker(env, task_queue_shared_vehicle).run())

### Comment out for public operator ####
# Rebalancing scheduler creates the charging schedule and relocations vehicle in the ridehailing fleet
rs_ridehailing_0 = RebalancingSchedulerRidehailing(
    distance_matrix,
    ride_hailing_fleet_0,
    global_config.ridehailing_operator_config.available_modes,
    global_config.ridehailing_operator_config.available_modes_supply,
    global_config.ridehailing_operator_config.number_of_service_workers,
    global_config.ridehailing_operator_config.base_regions,
    global_config.ridehailing_operator_config.base_capacity,
    global_config.ridehailing_operator_config.recharge_threshold,
    charging_infrastructure._charging_stations,
)

# Ridehailing operator manages all operations belonging to the ridehailing fleet
ops_ridehailing_0 = OperationsRidehailing(
    env,
    ride_hailing_fleet_0,
    global_config.ridehailing_operator_config.operations_start,
    global_config.ridehailing_operator_config.operations_duration,
    rs_ridehailing_0,
    payment_engine["ride_hailing_0"],
    global_config.ridehailing_operator_config.available_modes,
    global_config.ridehailing_operator_config.available_modes_supply,
    global_config.ridehailing_operator_config.recharge_threshold,
    task_queue_ridehailing,
    charging_infrastructure._charging_stations,
)

# Relocation scheduler creates the charging schedule and relocates vehicles in the shared mobility fleet
relocation_scheduler = RelocationScheduler(
    distance_matrix,
    mixed_fleet,
    global_config.shared_vehicle_operator_config.available_modes,
    global_config.shared_vehicle_operator_config.available_modes_supply,
    global_config.shared_vehicle_operator_config.number_of_service_workers,
    global_config.shared_vehicle_operator_config.base_regions,
    global_config.shared_vehicle_operator_config.base_capacity,
)

# Shared operator manages all operations belonging to the shared mobility fleet
shared_operator = Operations(
    env,
    mixed_fleet,
    global_config.shared_vehicle_operator_config.number_of_service_workers,
    global_config.shared_vehicle_operator_config.operations_start,
    global_config.shared_vehicle_operator_config.operations_duration,
    relocation_scheduler,
    payment_engine["shared_vehicle"],
    global_config.shared_vehicle_operator_config.available_modes,
    global_config.shared_vehicle_operator_config.available_modes_supply,
    global_config.shared_vehicle_operator_config.recharge_threshold,
    task_queue_shared_vehicle,
)

### Finish commenting out for public operator ####

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

# Start operations for ridehailing fleet
env.process(ops_ridehailing_0.timer())
env.process(ops_ridehailing_0.run_operations())

# Shared Operator cannot deal with zero transactions, comment this part out while running a ridehailing fleet/public operator
# Start operations for shared fleet
# env.process(shared_operator.timer())
# env.process(shared_operator.run_operations())

# Start operations for public operator
env.process(public_operator._run())

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
# env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

# env.run(until=end_time)

# logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})


### Things to do while changing the mode: ####

# - Modify population factory (just comment out the other pop factories)
# - To run RideHailing fleet comment out the running of the shared operator
# - Switch to the correct payment engine
# - Comment out all the operator modules from other fleets for the public operator


def run_simulation(end_time, seed=4711, env=env):
    # Before a new simulation run, reset everything
    User.user_id = 0
    SharedCar.car_id = 0
    SharedKickScooter.shared_kick_scooter_id = 0
    SharedScooter.shared_scooter_id = 0
    DemandFactory.counter = 0
    Vehicle.vehicle_id = 0
    PublicTransitVehicle.public_transit_vehicle_id = 0
    Bus.bus_id = GeodesicEnvironment.getInstance().reset_random_generator(seed)

    # Inject Simulation Environment to Logger (such that we can log the env time)
    cf = SimulationContextFilter(filter_name="add_env", extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    for sw in range(
        global_config.ridehailing_operator_config.number_of_service_workers
    ):
        env.process(ServiceWorker(env, task_queue_ridehailing).run())

    # for sw in range(global_config.shared_vehicle_operator_config.number_of_service_workers):
    #    env.process(ServiceWorker(env, task_queue_shared_vehicle).run())

    env.process(ops_ridehailing_0.timer())
    env.process(ops_ridehailing_0.run_operations())

    # env.process(shared_operator.timer())
    # env.process(shared_operator.run_operations())

    # env.process(public_operator._run())

    # Use only if the configuration parameters stay unchanged to avoid reloading everytime. Reload demand factory if the demand profile is different between consecutive runs
    demand_factory.reset()

    env.process(demand_factory.generate_demand())

    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    # Run simulation

    env.run(until=end_time)

    logging.warning("Ending Simulation.", extra={"clazz": "main", "oid": ""})


# sum_iterations = 3
# for i in range(sum_iterations):
#     env = simpy.Environment(start_time)

#     run_simulation(end_time=end_time)


### Things to do while changing the mode: ####

# - Modify population factory (just comment out the other pop factories)
# - To run RideHailing fleet comment out the running of the shared operator
# - Switch to the correct payment engine
# - Comment out all the operator modules from other fleets for the public operator
