##Imports
# Standard library imports
import logging
import os
import sys
import time
from configparser import ConfigParser
from datetime import datetime
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
from simulation.operator.fleet_factory import generate_AV_fleet
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
file_log_level = parser.get("SETTINGS", "file_log_level")

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)

logger = logging.getLogger()

output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d_%H:%M:%S")
# Record the start time
real_start_time = time.time()

# Make it beautiful
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
    filename=f"data/output/logs/{output_timestamp}.log",
    encoding="utf-8",
    level=file_log_level,  # set it to lowest so the handlers can decide
)

# Add Custom Init Filters (which work without the ENV obj)
cf = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf)

consolehandler = logging.StreamHandler()
consolehandler.setLevel(log_level)
consolehandler.addFilter(cf)
logger.addHandler(consolehandler)

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

#### TODO: when we have only AV, we should get rid of all the AV vs HV stuff
MoD_interval_reduction = 0  # By choice
global_config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction)
# A score that represents how much users trust autonomous vehicles. Not relevant for every simulation
AV_trust = parser.get("MODE_CHOICE_MODEL", "AV_trust").split(",")
AV_trust = [float(x) for x in AV_trust]


if mode_choice_strategy == "substitution":
    vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
        ["AutonomousCar"]
    )  ## Needs to be modified depending on the modus

else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# RideHailing Fleet Configuration         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Initialize config for different vehicle types
vehicle_type = "AUTONOMOUS_CAR"

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
global_config.add_ridehailing_vehicle_config("AutonomousCar", rvc)
global_config.add_ridehailing_vehicle_config("RideHailingCar", rvc)

# Number of autonomous cars in the fleet
n_autonomous_cars = parser.getint("RIDE_HAILING", "N_AUTONOMOUS_CARS")
# Not sure what this is for
allocation = parser.get("RIDE_HAILING", "ALLOCATION")

AV_penetration = parser.getfloat("SUPPLY", "AV_penetration")
EV_penetration = parser.getfloat("SUPPLY", "EV_penetration")

# price params
AV_price_reduction = parser.getfloat("RIDE_HAILING", "AV_PRICE_REDUCTION")
discount_rate = parser.getint("RIDE_HAILING", "DISCOUNT_RATE")
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

available_modes = parser.get("RIDE_HAILING", "AVAILABLE_VEHICLE_MODES_RIDEHAILING")
available_modes = available_modes.split(",")
available_modes_supply = [n_autonomous_cars]

rhoc = RideHailingOperatorConfig(
    recharge_threshold=recharge_threshold,
    operations_start=operations_start,
    operations_duration=operations_duration,
    vehicle_relocation_velocity=vehicle_relocation_velocity,
    available_modes=available_modes,
    available_modes_supply=available_modes_supply,
    n_autonomous_cars=n_autonomous_cars,
    n_ridehailing_cars=0,
    allocation=allocation,
)

global_config.add_ridehailing_operator_config(rhoc)
global_config.add_tech_penetration(EV_penetration, AV_penetration)
global_config.add_AV_trust(AV_trust)
global_config.add_ride_hailing_info(
    driver_payment_share, AV_price_reduction, price_params
)

# Bidding Streategy Parameters
bid_default = parser.getfloat("RIDE_HAILING_OPERATOR", "BID_DEFAULT")
bid_decay = parser.getfloat("RIDE_HAILING_OPERATOR", "BID_DECAY")
bidding_parameters = {"bid_default": bid_default, "bid_decay": bid_decay}

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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

tracking = Tracking.init(env)


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

# track charging stations
charging_stations_track = []


def track_charging_stations():
    while True:
        yield env.timeout(1)
        values = [
            {
                "time": env._now,
                "_location": d["_location"],
                "_plugs.count": d["_plugs"].count,
            }
            for d in [
                tracking.dump(x)[1] for x in tracking.list_tracked("ChargingStation")
            ]
        ]
        charging_stations_track.extend(values)


env.process(track_charging_stations())


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

available_vehicle_modes_ridehailing = ["AutonomousCar"]
available_vehicle_modes_supply_ride_hailing = [n_autonomous_cars]

ride_hailing_fleet_0 = generate_AV_fleet(env, supply_prob, n_autonomous_cars, seed=4711)

ride_hailing_fleet_1 = generate_AV_fleet(env, supply_prob, n_autonomous_cars, seed=4711)

# track vehicles in fleets
vehicles_track = []


def track_fleets(fleet_id):
    while True:
        yield env.timeout(1)
        envtime, values = (
            env._now,
            {
                "_fleet": fleet_id,
                "_state": [
                    tracking.get(x, "_state")[1]
                    for x in tracking.list_tracked("RideHailingAV")
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
                "_current_state_of_charge": [
                    tracking.get(x, "_current_state_of_charge")[1]
                    for x in tracking.list_tracked("RideHailingAV")
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
                "_vdt": [
                    tracking.get(x, "_vdt")[1]
                    for x in tracking.list_tracked("RideHailingAV")
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
            },
        )
        vehicles_track.append({"time": envtime, **values})


env.process(track_fleets(ride_hailing_fleet_0.id))
env.process(track_fleets(ride_hailing_fleet_1.id))


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

env.run(until=end_time - 1e-8)
world.simulation_finished.succeed()
env.run(until=end_time)

logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Save Tracking Data                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

pd.DataFrame.from_records(vehicles_track).to_csv(
    f"data/output/tracking/{output_timestamp}_vehicles.csv", index=False
)

pd.DataFrame.from_records(charging_stations_track).to_csv(
    f"data/output/tracking/{output_timestamp}_charging_stations.csv", index=False
)

avg_infra_util = (
    pd.DataFrame.from_records(charging_stations_track)["_plugs.count"]
    / charging_station_capacity[0]
).mean()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Save Transaction Data                   #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

fleet_0_transactions = ridehailing_operator_0.get_transactions()
fleet_1_transactions = ridehailing_operator_1.get_transactions()

fleet_0_transactions.to_csv(
    f"data/output/transactions/{output_timestamp}_fleet_0_transactions.csv", index=False
)
fleet_1_transactions.to_csv(
    f"data/output/transactions/{output_timestamp}_fleet_1_transactions.csv", index=False
)

service_rate_fleet_0 = (
    fleet_0_transactions["state"].value_counts()["Fulfilled"]
    / fleet_0_transactions.shape[0]
)

service_rate_fleet_1 = (
    fleet_1_transactions["state"].value_counts()["Fulfilled"]
    / fleet_1_transactions.shape[0]
)

fleet_0_task_transactions = ridehailing_operations_0.task_transactions
fleet_1_task_transactions = ridehailing_operations_1.task_transactions

fleet_0_task_transactions.to_csv(
    f"data/output/transactions/{output_timestamp}_fleet_0_task_transactions.csv",
    index=False,
)
fleet_1_task_transactions.to_csv(
    f"data/output/transactions/{output_timestamp}_fleet_1_task_transactions.csv",
    index=False,
)

# write down the configs used for that run
import csv

# Open the CSV file in append mode
with open("data/output/run_configs.csv", "a", newline="\n", encoding="utf-8") as file:
    # Create a CSV writer object
    writer = csv.writer(file)

    # Write a row to the CSV file
    writer.writerow(
        [
            output_timestamp,
            os.path.basename(__file__),
            end_time,
            time.time() - real_start_time,
            n_autonomous_cars,
            number_of_charging_locations,
            charging_station_capacity[0],
            charging_station_power[0],
            seed,
            service_rate_fleet_0,
            service_rate_fleet_1,
            avg_infra_util,
            None,
            "random_SOC_init" if initial_SoC == 0 else None,
        ]
    )
