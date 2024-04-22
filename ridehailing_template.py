##Imports
# Standard library imports
import os
import sys
from pathlib import Path
from configparser import ConfigParser
import logging

# Third-party library imports
import simpy
import pandas as pd
import numpy as np

# Custom module imports
from utils import load_environment
from tracking.tracking import Tracking

# Imports world related modules
from simulation.agent.user import User
from simulation.world.world import World
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    Configuration,
    ModeChoiceConfig,
    RideHailingOperatorConfig,
    PopulationConfig,
    RideHailingVehicleConfig,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import vehicle types and vehicle choice options
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import (
    OnlyCarVehicleChoiceBehavior,
)

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import ChargingInfrastructureConfig
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)

# Import operator related modules
from simulation.operator.fleet_factory import (
    generate_mixed_ride_hailing_fleet,
    generate_ridehailing_fleet_config,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.operator.operations_management.operations_ridehailing import (
    OperationsRidehailing,
)
from simulation.operator.operations_management.rebalancing_scheduler_ridehailing import (
    RebalancingSchedulerRidehailing,
)
from simulation.operator.operations_management.task_queue import TaskQueue

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
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")
# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

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
# Maximumn pickuo distance that is ok for the users
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
    round(float(x) * n_ridehailing_cars * (1 - AV_penetration))
    for x in drivers_availability
]
available_modes = parser.get("RIDE_HAILING", "available_vehicle_modes_ridehailing")
available_modes = available_modes.split(",")
available_modes_supply = [n_ridehailing_cars, n_autonomous_cars]

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

env = simpy.Environment(initial_time=0)

# Population Type
# TODO: Generate population for multiple modes at once --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/52
population_factory = PopulationFactory(pop_prob_ridehailing, seed)

# Load Spatial Environment
load_environment()

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
cf_init = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf_init)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
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
DemandFactory.counter = 0
# Add a counter for ridehailing car too

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

search_engine = {"ride_hailing_0": RideHailingSearchEngine(env)}

payment_engine = search_engine

vehicle_assignment_engine = {"ride_hailing_0": RideHailingAllocationEngine(env)}

# Configure and generate / spawn fleet vehicles
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

# Add the fleet to the search engine
search_engine["ride_hailing_0"].register_fleet(ride_hailing_fleet_0)

# Initialize task queues
task_queue_ridehailing = TaskQueue(env)

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
    charging_infrastructure._chargers,
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
    charging_infrastructure._chargers,
)

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

# Start operations
env.process(ops_ridehailing_0.timer())
env.process(ops_ridehailing_0.run_operations())


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

env.run(until=50)

logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})
