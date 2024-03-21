### This is the template for a simulation with a ridehailing and shared mobility fleet. #####

##Imports 
# Standard library imports
import os
import sys
from pathlib import Path
from configparser import ConfigParser
import logging

# Third-party library imports
import simpy
import random
import pandas as pd
import numpy as np
import geopandas as gpd

# Custom module imports
from utils import load_environment
from configparser import ConfigParser
from tracking.tracking import Tracking

# Imports world related modules
from simulation.agent.user import User 
from simulation.world.world import World
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.population.PopulationFactory import PopulationFactory

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import Configuration, ModeChoiceConfig, VehicleConfig, SharedVehicleOperatorConfig
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import vehicle types and vehicle choice options
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import OnlyCarVehicleChoiceBehavior

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import DistanceMatrixImporter
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import ChargingInfrastructureConfig
from simulation.infrastructure.charging_stations.charging_infastructure import ChargingInfrastructure

# Import operator related modules
from simulation.operator.fleet_factory import generate_mixed_fleet, generate_fleet_config
from simulation.operator.fleet_factory import generate_mixed_ride_hailing_fleet, generate_ridehailing_fleet_config
from simulation.operator.shared_vehicle_allocation_engine import SharedVehicleAllocationEngine
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.operator.ride_hailing_allocation_engine import RideHailingAllocationEngine
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.operator.operations_management.relocation_scheduler import RelocationScheduler
from simulation.operator.operations_management.operations_ridehailing import OperationsRidehailing
from simulation.operator.operations_management.rebalancing_scheduler_ridehailing import RebalancingSchedulerRidehailing
from simulation.operator.operations_management.operations import Operations
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.operator.operations_management.service_worker import ServiceWorker

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
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")
# Get the supply probability from supply file
supply_prob = pd.read_csv(supply_file_path)

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

pop_prob_ridehailing = parser.get("RIDE_HAILING", "population_probabilities").split(',')
pop_prob_ridehailing = [float(x) for x in pop_prob_ridehailing]
pop_prob_sharedvehicle = parser.get("SHARED_VEHICLE_OPERATOR", "population_probabilities").split(',')
pop_prob_sharedvehicle = [float(x) for x in pop_prob_sharedvehicle]

mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")

mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(',')

###### Registering available modes does not make sense anymore since each operator gets its own available vehicle modes #####
# For example: Shared operator gets SharedCar, SharedScooter, SharedKickScooter and eventually SharedBike
#              Ridehailing operator gets RideHailingCar, AutonomousCar
mc = ModeChoiceConfig(mode_choice_strategy, mode_choice_sub_boundary, mode_choice_available_modes,
                      mode_choice_model_path)

global_config.add_mode_choice_config(mc)


# TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/51
if mode_choice_strategy == "substitution":
     vehicle_choice_model = OnlyCarVehicleChoiceBehavior(['SharedScooter','SharedKickScooter','SharedCar'])
     #vehicle_choice_model = OnlyCarVehicleChoiceBehavior(['AutonomousCar','RideHailingCar']) ## Needs to be modified depending on the modus

else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Shared Vehicle Fleet Configuration      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: Implement SharedBikes --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/46
# TODO: SharedScooters and SharedKickScooters do not have an initial state of charge. They start with the max state of charge.
for idx, vehicle_type in enumerate(["SHARED_CAR", "SHARED_SCOOTER", "SHARED_KICK_SCOOTER"]):
    vehicle_type_classes = ["SharedCar", "SharedScooter", "SharedKickScooter"]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    max_walking_distance = parser.getint(vehicle_type, "WALKING_DISTANCE")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")
    if vehicle_type == "SHARED_CAR":
        initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC")

    vc = VehicleConfig(price_per_min, max_state_of_charge, energy_consumption, velocity, max_available_seats,
                       max_walking_distance, daily_total_cost, initial_SoC)
    global_config.add_vehicle_config(vehicle_type_classes[idx], vc)

# Needs to be modified depending on the mode
# Vehicles whose state of charge is below the threshold value are to be charged
recharge_threshold_shared_vehicle = parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD") / 100 
global_config.add_recharging_threshold(recharge_threshold_shared_vehicle)

charging_station_power_shared_vehicle = parser.getfloat("SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER") # Think about moving this to charging infrastructure
# Service workers relocate the vehicles and bring them to charging stations
number_of_service_workers_shared_vehicle = parser.getint("SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER")
# Base regions are city parts in which these service workers operate
number_of_base_regions_shared_vehicle = parser.getint("SHARED_VEHICLE_OPERATOR", "NUMBER_OF_BASE_REGIONS")
# Base regions are defined as hexagons in the city
base_regions_shared_vehicle = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
base_regions_shared_vehicle = base_regions_shared_vehicle.split(',')[:number_of_base_regions_shared_vehicle]

# Base capacity is the number of charging stations in the charging hub
base_capacity_shared_vehicle = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
operations_start_shared_vehicle = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
operations_duration_shared_vehicle = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity_shared_vehicle = parser.getint("SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY")

svoc = SharedVehicleOperatorConfig(recharge_threshold_shared_vehicle, charging_station_power_shared_vehicle,
                                   number_of_service_workers_shared_vehicle, base_regions_shared_vehicle,
                                   base_capacity_shared_vehicle, operations_start_shared_vehicle, operations_duration_shared_vehicle,
                                   vehicle_relocation_velocity_shared_vehicle)

# Get number of each vehicle type to be spawned from configuration (Maybe move it to the shared vehicle operator?)
n_cars = parser.getint("EXPERIMENT_MANAGEMENT", "N_CARS")
n_kick_scooter = parser.getint("EXPERIMENT_MANAGEMENT", "N_KICKSCOOTER")
n_bikes = parser.getint("EXPERIMENT_MANAGEMENT", "N_BIKES")
n_scooter = parser.getint("EXPERIMENT_MANAGEMENT", "N_SCOOTER")

available_vehicle_modes_shared_vehicle = parser.get("SHARED_VEHICLE_OPERATOR", "available_vehicle_modes_shared_vehicle")
available_vehicle_modes_shared_vehicle = available_vehicle_modes_shared_vehicle.split(',')
available_vehicle_modes_supply_shared_vehicle = [n_cars, n_scooter, n_kick_scooter, n_bikes]

# Register all configurations
global_config.add_shared_vehicle_operator_config(svoc)

#### Not sure if this part is necessary #####
MoD_interval_reduction = 0 # By choice
global_config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction) # Not sure if we need this

###### End Shared Vehicle Fleet Configuration ######

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# RideHailing Fleet Configuration         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Number of ridehailing cars in the fleet
n_ridehailing_cars = parser.getint("RIDE_HAILING", "n_ridehailing_cars")
# Number of autonomous cars in the fleet
n_autonomous_cars = parser.getint("RIDE_HAILING", "n_autonomous_cars")
# Not sure what this is for 
allocation = parser.get("RIDE_HAILING", "ALLOCATION")
# A score that represents how much users trust autonomous vehicles. Not relevant for every simulation
AV_trust = parser.get("MODE_CHOICE_MODEL", "AV_trust").split(',')
AV_trust = [float(x) for x in AV_trust]
AV_price_reduction = parser.getfloat("RIDE_HAILING", "AV_PRICE_REDUCTION")
discount_rate = parser.getint("RIDE_HAILING", "DISCOUNT_RATE")

AV_penetration = parser.getfloat('SUPPLY', "AV_penetration")
EV_penetration = parser.getfloat('SUPPLY', "EV_penetration")
# Drivers share of the revenue made with each ride
driver_payment_share = parser.getfloat('RIDE_HAILING', "DRIVER_PAYMENT_SHARE")
price_params_ride_hailing = parser.get('RIDE_HAILING', "PRICE_PARAMS")
price_params_ride_hailing = price_params_ride_hailing.split(',')
price_params_ride_hailing = [float(x) * (1 - discount_rate) for x in price_params_ride_hailing]
# Maximumn pickuo distance that is ok for the users
distance_threshold_ridehailing = parser.getfloat('RIDE_HAILING', "MAX_PICKUP_DISTANCE")
global_config.add_distance_threshold_to_user(distance_threshold_ridehailing)
# Vehicles whose state of charge is below the threshold value are to be charged
recharge_threshold_ridehailing  = parser.get("RIDE_HAILING_OPERATOR", "RECHARGE_THRESHOLD").split(',')
recharge_threshold_ridehailing = [float(x) / 100 for x in recharge_threshold_ridehailing]

#TODO: Separate configurations --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/49
#global_config.add_recharging_threshold(recharge_threshold_ridehailing)

charging_station_power_ridehailing = parser.getfloat("RIDE_HAILING_OPERATOR", "CHARGING_STATION_POWER") ### Maybe this should belong to charging infrastructure?
# Service workers relocate the vehicles and bring them to charging stations
number_of_service_workers_ridehailing = parser.getint("RIDE_HAILING_OPERATOR", "NUMBER_OF_SERVICE_WORKER")
# Base regions are city parts in which these service workers operate
number_of_base_regions_ridehailing = parser.getint("RIDE_HAILING_OPERATOR", "NUMBER_OF_BASE_REGIONS")
# Base regions are defined as hexagons in the city
base_regions_ridehailing = parser.get("RIDE_HAILING_OPERATOR", "BASE_REGIONS")
base_regions_ridehailing = base_regions_ridehailing.split(',')[:number_of_base_regions_ridehailing]

# Base capacity is the number of charging stations in the charging hub
base_capacity_ridehailing = parser.getint("RIDE_HAILING_OPERATOR", "BASE_CAPACITY")
operations_start_ridehailing = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_START")
operations_duration_ridehailing = parser.getint("RIDE_HAILING_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity_ridehailing = parser.getint("RIDE_HAILING_OPERATOR", "VEHICLE_RELOCATION_VELOCITY")

# Read drivers availability distribution
drivers_availability = parser.get('SUPPLY', "RH_availability").split(',')
drivers_availability = [round(float(x) * n_cars * (1 - AV_penetration)) for x in drivers_availability]

available_vehicle_modes_ridehailing = parser.get("RIDE_HAILING", "available_vehicle_modes_ridehailing")
available_vehicle_modes_ridehailing = available_vehicle_modes_ridehailing.split(',')
available_vehicle_modes_supply_ride_hailing = [n_ridehailing_cars, n_autonomous_cars]

global_config.add_tech_penetration(EV_penetration, AV_penetration)
global_config.add_AV_trust(AV_trust)
global_config.add_driver_availability_vector(drivers_availability)
global_config.add_ride_hailing_info(driver_payment_share, AV_price_reduction, price_params_ride_hailing)

###### End RideHailing Fleet Configuration ######

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=0)

# Population Type
# TODO: Generate population for multiple modes at once --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/52
#population_factory = PopulationFactory(pop_prob_ridehailing, seed)
population_factory = PopulationFactory(pop_prob_sharedvehicle, seed)

# Load Spatial Environment
load_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Charging Infrastructure                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #
# Doubled Code --> actually the same as number of base capacity
number_of_charging_stations = parser.getint("Charging_Infrastructure", "NUMBER_OF_CHARGING_STATIONS")
charging_location_list = parser.get("Charging_Infrastructure", "BASE_REGIONS").split(',')[
                             :number_of_charging_stations]

charging_power = parser.getint("Charging_Infrastructure", "CHARGING_POWER")
charging_capacity = parser.getint("Charging_Infrastructure", "CHARGING_CAPACITY")
charging_power_list = list(np.zeros(len(charging_location_list)) + charging_power)
charging_capacity_list = list(np.zeros(len(charging_location_list)) + charging_capacity)
sic = ChargingInfrastructureConfig(charging_location_list, charging_power_list, charging_capacity_list)
charging_infrastructure = ChargingInfrastructure(env, charging_location_list, charging_power_list, charging_capacity_list, reset=True)

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

import logging

# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

logger = logging.getLogger()
logger.setLevel(log_level)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s')
file_handler = logging.FileHandler('report.log')
file_handler.setFormatter(formatter)
file_handler.setLevel(log_level)

# Add Custom Init Filters (which work without the ENV obj)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
cf_init = SimulationContextFilter(filter_name='add_env', extra=[])
logger.addFilter(cf_init)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name='add_env', extra=env)
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
di = DemandImporter(spatial_resolution=global_config.spatial_resolution,
                    temporal_resolution=global_config.temporal_resolution,
                    daily_resolution=global_config.daily_resolution,
                    city=global_config.city)

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

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Modules                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

search_engine = {'ride_hailing_0': RideHailingSearchEngine(env), 
                 'shared_vehicle': SharedVehicleSearchEngine(env)}

payment_engine = search_engine

vehicle_assignment_engine = {'ride_hailing_0': RideHailingAllocationEngine(env),
                             'shared_vehicle': SharedVehicleAllocationEngine(env)}

# Configure and generate / spawn fleet vehicles
# Shared Vehicle Fleet
shared_vehicle_fleet_config = generate_fleet_config(supply_prob, n_cars = n_cars, n_scooter = n_scooter, n_kick_scooter= n_kick_scooter, n_bikes=n_bikes)
mixed_fleet = generate_mixed_fleet(env, shared_vehicle_fleet_config)

# Ride Hailing Fleet
ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(distribution=supply_prob, n_cars=n_ridehailing_cars,
                                                                    n_AVs=n_autonomous_cars, allocation_method='historical',
                                                                    allocation=allocation)
ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(env, ride_hailing_fleet_config_0)

# Add the fleets to the search engine
search_engine['shared_vehicle'].register_fleet(mixed_fleet)
search_engine['ride_hailing_0'].register_fleet(ride_hailing_fleet_0)

# Initialize task queues for both fleets
task_queue_ridehailing = TaskQueue(env)
task_queue_shared_vehicle = TaskQueue(env)

# Spawn Service Workers for the Shared Fleet
for sw in range(global_config.shared_vehicle_operator_config.number_of_service_worker):
    env.process(ServiceWorker(env, task_queue_shared_vehicle).run())

# Rebalancing scheduler creates the charging schedule and relocations vehicle in the ridehailing fleet
rs_ridehailing_0 = RebalancingSchedulerRidehailing(distance_matrix, ride_hailing_fleet_0,
                                                    available_vehicle_modes_ridehailing,
                                                    available_vehicle_modes_supply_ride_hailing, number_of_service_workers_ridehailing,
                                                    base_regions_ridehailing, base_capacity_ridehailing, recharge_threshold_ridehailing,
                                                    charging_infrastructure._chargers)

# Ridehailing operator manages all operations belonging to the ridehailing fleet
ops_ridehailing_0 = OperationsRidehailing(env, ride_hailing_fleet_0,
                                              operations_start_ridehailing,
                                              operations_duration_ridehailing,
                                              rs_ridehailing_0,
                                              payment_engine['ride_hailing_0'], available_vehicle_modes_ridehailing,
                                              available_vehicle_modes_supply_ride_hailing,
                                              recharge_threshold_ridehailing,
                                              task_queue_ridehailing, charging_infrastructure._chargers)

# Relocation scheduler creates the charging schedule and relocates vehicles in the shared mobility fleet
relocation_scheduler = RelocationScheduler(distance_matrix, mixed_fleet, available_vehicle_modes_shared_vehicle,
                            available_vehicle_modes_supply_shared_vehicle, number_of_service_workers_shared_vehicle,
                            base_regions_shared_vehicle, base_capacity_shared_vehicle)

# Shared operator manages all operations belonging to the shared mobility fleet
shared_operator = Operations(env, mixed_fleet, number_of_service_workers_shared_vehicle, operations_start_shared_vehicle,
                    operations_duration_shared_vehicle, relocation_scheduler,
                    payment_engine["shared_vehicle"], available_vehicle_modes_shared_vehicle, ### What to do with the available modes?
                    available_vehicle_modes_supply_shared_vehicle, recharge_threshold_shared_vehicle, task_queue_shared_vehicle)

# Initialize World
world = World.init(env, search_engine, payment_engine, vehicle_assignment_engine, vehicle_choice_model, # Again the problem with different modes is here
                       population_factory, charging_infrastructure, reset=True)

# Start operations
env.process(ops_ridehailing_0.timer())
env.process(ops_ridehailing_0.run_operations())

# Shared Operator cannot deal with zero transactions, comment this part out while running a ridehailing fleet
env.process(shared_operator.timer())
env.process(shared_operator.run_operations())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Spawn Demand Processes.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# TODO: we need to have a look at https://github.com/IS3UniCologne/urban-mobility-simulation/issues/32
# for now, we spawn by chance
demand_factory = DemandFactory(env, demand_profile, di, world, [], seed, mode="shared_vehicle")
env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

logging.warning(f"Starting Simulation.",
                    extra={"clazz": "main", "oid": ""})

env.run(until=50)

logging.warning(f"Simulation Finished.",
                    extra={"clazz": "main", "oid": ""})

###### Ongoing Issues/Questions of/about the Current State: ######

# 1. Available vehicle modes are separated into shared vehicle fleet and ridehailing fleet. Should these be united under mode choice available modes? 
#    Need to take a deeper look into how different operators deal with different modes. Is it possible to initialize all available modes once? But then how does the shared vehicle operator
#    react to a RideHailingCar?

# 2. There is only one charging infrastructure that is used by both fleets but than both fleets have their own charging stations with the exact same parameters. Should it stay this way or should the fleets also share the charging stations 
#    or have different infrastructure configurations?
#    When they share the same infrastructure, how do we communicate between fleets that the charging stations are occupied by the other fleet?

# 3. In this version very few parameters are registered to the config since there are shared_vehicle / ridehailing versions of these. For example: recharge_threshold_shared_vehicle
#                                                                                                                                                  recharge_threshold_ridehailing
#    - We should either add these different versions to the global config
#    - Or leave registering these which would almost mean that we stop registering completely but only register those that are used by other modules from the config

# 4. Basic idea for the template was to start the operations of both fleets and generate demand for only one fleet. But the Relocation Scheduler needs the transactions dataframe to calculate the estimated demand 
#    per hexagon to create a charging plan. For now we do not start the operations of the Relocation Scheduler but we should probably think of how the Relocation Scheduler handles the situation when there aren't any transactions, or
#    we leave it for now until we can generate demand for multiple modes.

# 5. Population factory cannot yet deal with different modes at the same time.


### Things to do while changing the mode: ####

# - Register only the charging threshold of the respective mode
# - Change the OnlyCarVehicleChoiceBehavior - modify the class too --> Shared Fleet has 3 attributes whereas RideHailing Fleet has 2
# - Modify population factory (just comment out the other pop factory)
# - To run RideHailing fleet comment out the running of the shared operator (Issue 4 on the list above)