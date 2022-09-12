from pathlib import Path
import pandas as pd
import numpy as np

from simulation.helper.configuration.configuration import Configuration, VehicleConfig, ModeChoiceConfig, \
    SharedVehicleOperatorConfig, ChargingInfrastructureConfig
from simulation.infrastructure.charging_stations.charging_infastructure import ChargingInfrastructure
from simulation.infrastructure.helper.distance_matrix_importer import DistanceMatrixImporter
from simulation.operator.fleet_factory import generate_fleet_config, generate_mixed_fleet, \
    generate_mixed_ride_hailing_fleet, generate_ridehailing_fleet_config
from simulation.operator.operations_management.operations import Operations
from simulation.operator.operations_management.operations_ridehailing import OperationsRidehailing
from simulation.operator.operations_management.rebalancing_scheduler_ridehailing import RebalancingSchedulerRidehailing
from simulation.operator.operations_management.relocation_scheduler import RelocationScheduler
from simulation.operator.operations_management.service_worker import ServiceWorker
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.vehicle_choice_model.distance_based_shared_vehicle_choice_behavior import \
    DistanceBasedSharedVehicleVehicleChoiceBehavior
from simulation.agent.user import User  # must come before DemandFactory, otherwise circular imports
from simulation.operator.ride_hailing_allocation_engine import RideHailingAllocationEngine
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import OnlyCarVehicleChoiceBehavior
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
pd.set_option('display.max_columns', None)
import simpy
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.operator.shared_vehicle_allocation_engine import SharedVehicleAllocationEngine
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
import geopandas as gpd

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Configuration from ini file.       #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

import sys
from configparser import ConfigParser
import os

# Change working directory to path of main.py
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

# World Config
spatial_res  = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")


# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand")
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(',')

# Input Files (Supply)
supply_file_path = parser.get("SUPPLY", "path_vehicle_supply")

# Environment files
bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res)

# Read Shared Vehicle Config and add to Global Config File
for idx, vehicle_type in enumerate(["SHARED_CAR", "SHARED_SCOOTER", "SHARED_KICK_SCOOTER"]):
    vehicle_type_classes = ["SharedCar", "SharedScooter", "SharedKickScooter"]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    max_walking_distance = parser.getint(vehicle_type, "WALKING_DISTANCE")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")

    vc = VehicleConfig(price_per_min, max_state_of_charge, energy_consumption, velocity, max_available_seats, max_walking_distance, daily_total_cost)
    global_config.add_vehicle_config(vehicle_type_classes[idx], vc)

# Read Mode Choice Configuration
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(',')

mc = ModeChoiceConfig(mode_choice_strategy, mode_choice_sub_boundary, mode_choice_available_modes, mode_choice_model_path)
global_config.add_mode_choice_config(mc)

# Read Shared Vehice Operator Config
recharge_threshold = parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD")
charging_station_power = parser.getfloat("SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER")
number_of_service_workers = parser.getint("SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER")
base_regions = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
base_regions = base_regions.split(',')
base_capacity = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
operations_start = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
operations_duration = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
vehicle_relocation_velocity = parser.getint("SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY")

svoc = SharedVehicleOperatorConfig(recharge_threshold, charging_station_power,
                                   number_of_service_workers, base_regions,
                                   base_capacity, operations_start, operations_duration,
                                   vehicle_relocation_velocity)
global_config.add_shared_vehicle_operator_config(svoc)

# Read Charging Infrastructure Config
charging_location_list = parser.get("Charging_Infrastructure", "BASE_REGIONS").split(',')
charging_power_list = parser.get("Charging_Infrastructure", "CHARGING_STATION_POWER").split(',')
charging_power_list = [float(x) for x in charging_power_list]
charging_capacity_list = parser.get("Charging_Infrastructure", "CHARGING_STATION_CAPACITY").split(',')
charging_capacity_list = [float(x) for x in charging_capacity_list]
sic = ChargingInfrastructureConfig(charging_location_list, charging_power_list, charging_capacity_list)
global_config.add_charging_infrastructure_config(sic)

# Output Configuration
store_results = parser.getboolean("OUTPUT", "persist_results")
output_folder = parser.get("OUTPUT", "output_folder")
transaction_file   = parser.get("OUTPUT", "transaction_file")
fleet_state_file   = parser.get("OUTPUT", "fleet_state_file")

global_config.set_store_results(store_results)
global_config.set_output_path(output_folder)
global_config.set_transaction_file(transaction_file)
global_config.set_fleet_state_file(fleet_state_file)

# Log Level
log_level = parser.get("SETTINGS", "log_level")

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Configure Logging.                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

import logging

# Make it beautiful
# logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

logger = logging.getLogger()
logger.setLevel(log_level)

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)

# Add Custom Init Filters (which work without the ENV obj)
cf_init = SimulationContextFilter(filter_name='add_env', extra=[])
logger.addFilter(cf_init)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Underlying Spatial Environment.    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

def load_environment():
    # Read Environment Files
    filename = bounding_box_path
    with open(filename) as file:
        env_df = gpd.read_file(file)

    filename = env_layer_hex_9
    with open(filename) as file:
        env_df_hex_9 = gpd.read_file(file, driver= "GeoJSON")
        env_df_hex_9.set_index('hex_id_9', inplace=True)

    filename = env_layer_hex_8
    with open(filename) as file:
        env_df_hex_8 = gpd.read_file(file)
        env_df_hex_8.set_index('hex_id_8', inplace=True)

    filename = env_layer_hex_7
    with open(filename) as file:
        env_df_hex_7 = gpd.read_file(file)
        env_df_hex_7.set_index('hex_id_7', inplace=True)

    geodesic_environment = GeodesicEnvironment()
    geodesic_environment.addLayer("bounding_box", env_df)
    geodesic_environment.addLayer("hex_9", env_df_hex_9)
    geodesic_environment.addLayer("hex_8", env_df_hex_8)
    geodesic_environment.addLayer("hex_7", env_df_hex_7)

    return geodesic_environment

# Load Spatial Environment
load_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Demand Data (once).                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

p = Path(demand_file_path)
di = DemandImporter(spatial_resolution=global_config.spatial_resolution,
                    temporal_resolution=global_config.temporal_resolution,
                    daily_resolution=global_config.daily_resolution)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(f"hex_{spatial_res}").index.tolist()
dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure")
distance_matrix = dmi.load_distance_matrix()


def run_single_simulation(start_time=0, end_time=20, n_cars=0, n_scooter=0, n_kick_scooter=0, seed=42, substitution=0.1,
                          price_sensitive_pop_prob=0.0, allocation=None, returnDataFrame=False):
    """
    :param start_time:
    :param end_time:
    :param n_cars:
    :param n_scooter:
    :param n_kick_scooter:
    :param seed:
    :param substitution:
    :param price_sensitive_pop_prob: 1.0 means only price sensitive users, 0.0 means only sustainable users
    :return:
    """
    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Setup Simulation Environment.           #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Simulation Environment
    env = simpy.Environment(initial_time=start_time)

    # Before each simulation run, reset counter and random number generators
    SharedCar.car_id = 0
    SharedKickScooter.shared_kick_scooter_id = 0
    SharedScooter.shared_scooter_id = 0
    User.user_id = 0
    DemandFactory.counter = 0

    GeodesicEnvironment.getInstance().reset_random_generator(seed)

    # Inject Simulation Environment to Logger (such that we can log the env time)
    cf = SimulationContextFilter(filter_name='add_env', extra=env)
    edf = ExtraDefaultFilter(filter_name="add_default_value")
    logger.addFilter(cf)
    logger.addFilter(edf)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. Simulation Modules.               #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Operator Modules
    search_engine = {'shared_vehicle': SharedVehicleSearchEngine(env), 'ride_hailing': RideHailingSearchEngine(env)}
    payment_engine = search_engine
    vehicle_assignment_engine = {'shared_vehicle': SharedVehicleAllocationEngine(env),
                                 'ride_hailing': RideHailingAllocationEngine(env)}
    # TODO: define separately for Ride-hailing
    if mode_choice_strategy == "substitution":
        vehicle_choice_model = OnlyCarVehicleChoiceBehavior(['RideHailingCar'])
    # Vehicle Choice Model
    # if mode_choice_strategy == "substitution":
    #     vehicle_choice_model = DistanceBasedSharedVehicleVehicleChoiceBehavior(mode_choice_model_path,
    #                                                                            substitution,
    #                                                                            mode_choice_available_modes)
    else:
        raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

    # Population Type
    population_factory = PopulationFactory(price_sensitive_pop_prob, seed)

    # Charging Infrastructure
    charging_infrastructure = ChargingInfrastructure(env, charging_location_list, charging_power_list,
                                                     charging_capacity_list)

    # World
    world = World.init(env, search_engine, search_engine, vehicle_assignment_engine, vehicle_choice_model,
                       population_factory, charging_infrastructure, reset=True)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Spawn Demand Processes.                 #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    # shared_vehicle_demand_factory = DemandFactory(env, demand_profile, di, world, demand_modifier_paths, seed,
    #                                               mode='shared_vehicle')
    #
    # env.process(shared_vehicle_demand_factory.generate_demand())

    ride_hailing_demand_factory = DemandFactory(env, demand_profile, di, world, demand_modifier_paths, seed,
                                                mode='ride_hailing')

    env.process(ride_hailing_demand_factory.generate_demand())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Load Vehicle Fleet and Place on World.  #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    supply_prob = pd.read_csv(supply_file_path)

    shared_vehicle_fleet_config_0 = generate_fleet_config(distribution=supply_prob, n_cars=0, n_scooter=0,
                                                          n_kick_scooter=0, n_bikes=0, allocation_method='historical',
                                                          allocation=allocation)
    shared_vehicle_fleet_0 = generate_mixed_fleet(env, shared_vehicle_fleet_config_0)

    ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(distribution=supply_prob, n_cars=n_cars, n_scooter=0,
                                                        n_kick_scooter=0, n_bikes=0, allocation_method='historical',
                                                        allocation=allocation)
    ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(env, ride_hailing_fleet_config_0)
    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Inject Modules.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    search_engine['shared_vehicle'].register_fleet(shared_vehicle_fleet_0)
    search_engine['ride_hailing'].register_fleet(ride_hailing_fleet_0)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Operations Management Processes         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    available_vehicle_modes = ["SharedKickScooter", "SharedScooter", "SharedCar"]
    available_vehicle_modes_ridehailing = ['RideHailingCar']
    available_vehicle_modes_supply = [n_kick_scooter, n_scooter, n_cars]
    available_vehicle_modes_supply_ride_hailing = [n_cars]
    no_service_workers = global_config.shared_vehicle_operator_config.number_of_service_worker
    base_regions = global_config.shared_vehicle_operator_config.base_regions
    base_capacity = global_config.shared_vehicle_operator_config.base_capacity

    # Initialize Rule Based Relocation Scheduler
    rs = RelocationScheduler(distance_matrix, shared_vehicle_fleet_0, available_vehicle_modes,
                             available_vehicle_modes_supply, no_service_workers,
                             base_regions, base_capacity)

    # For RideHailing Fleets
    rs_ridehailing = RebalancingSchedulerRidehailing(distance_matrix, ride_hailing_fleet_0, available_vehicle_modes_ridehailing,
                             available_vehicle_modes_supply_ride_hailing, no_service_workers,
                             base_regions, base_capacity, recharge_threshold, charging_infrastructure._chargers)

    # Store Tasks which are processed by service workers
    task_queue = TaskQueue(env)
    task_queue_ridehailing = TaskQueue(env)

    # Init Operations Module
    ops = Operations(env, shared_vehicle_fleet_0, no_service_workers,
                     global_config.shared_vehicle_operator_config.operations_start,
                     global_config.shared_vehicle_operator_config.operations_duration, rs,
                     payment_engine['shared_vehicle'], available_vehicle_modes,
                     available_vehicle_modes_supply, global_config.shared_vehicle_operator_config.recharge_threshold,
                     task_queue)

    ops_ridehailing = OperationsRidehailing(env, ride_hailing_fleet_0,
                     global_config.shared_vehicle_operator_config.operations_start,
                     global_config.shared_vehicle_operator_config.operations_duration, rs_ridehailing,
                     payment_engine['ride_hailing'], available_vehicle_modes_ridehailing,
                     available_vehicle_modes_supply_ride_hailing, global_config.shared_vehicle_operator_config.recharge_threshold,
                     task_queue_ridehailing, charging_infrastructure._chargers)

    # env.process(ops.timer())
    # env.process(ops.run_operations())
    env.process(ops_ridehailing.timer())
    env.process(ops_ridehailing.run_operations())

    # Spawn Service Workers
    # for sw in range(no_service_workers):
    #     env.process(ServiceWorker(env, task_queue).run())
    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Run Simulation.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    logging.warning(f"Starting Simulation.",
                    extra={"clazz": "main", "oid": ""})

    env.run(until = end_time)

    logging.warning(f"Simulation Finished.",
                    extra={"clazz": "main", "oid": ""})
    total_cost_per_day = {}
    # Daily Total Cost (CAPEX+OPEX) (cost derived from RevCalc excel in iCloud folder)
    total_cost_per_day['shared_vehicle'] = (global_config.get_vehicle_config("SharedCar").daily_total_cost * n_cars
                                            + global_config.get_vehicle_config(
                "SharedScooter").daily_total_cost * n_scooter
                                            + global_config.get_vehicle_config(
                "SharedKickScooter").daily_total_cost * n_kick_scooter) * (end_time / 1440)

    # print("Total Revenue: " + str(payment_engine.total_revenue))
    # print("Total Costs: " + str(total_cost_per_day_shared_vehicle))
    # print("Profit: " + str(payment_engine.total_revenue-total_cost_per_day_shared_vehicle))

    # print("Total Fulfilled Trips: " + str(payment_engine.total_fulfilled_trips))
    # print("Total Missed Trips: " + str(payment_engine.total_missed_trips))
    # print("Total Missed Revenue: " + str(payment_engine.total_missed_revenue))
    # TODO: fix it (maybe remove it)
    total_cost_per_day['ride_hailing'] = (global_config.get_vehicle_config("SharedCar").daily_total_cost * n_cars
                                          + global_config.get_vehicle_config(
                "SharedScooter").daily_total_cost * n_scooter
                                          + global_config.get_vehicle_config(
                "SharedKickScooter").daily_total_cost * n_kick_scooter) * (end_time / 1440)
    no_vehicles_to_be_charged = {}
    no_vehicles_to_be_charged['shared_vehicle'] = shared_vehicle_fleet_0.get_all_vehicles_below_soc_level \
                                                      (global_config.shared_vehicle_operator_config.recharge_threshold)
    no_vehicles_to_be_charged['ride_hailing'] = ride_hailing_fleet_0.get_all_vehicles_below_soc_level(
        global_config.shared_vehicle_operator_config.recharge_threshold)
    # print("Number of Vehicles to be charged: " + str(no_vehicles_to_be_charged_shared_vehicle))

    # Final Objective Function for Heuristic Search
    func_objective = {}
    func_objective['shared_vehicle'] = payment_engine['shared_vehicle'].total_revenue - total_cost_per_day[
        'shared_vehicle'] - \
                                       payment_engine['shared_vehicle'].total_missed_revenue
    func_objective['ride_hailing'] = payment_engine['ride_hailing'].total_revenue - total_cost_per_day['ride_hailing'] - \
                                     payment_engine['ride_hailing'].total_missed_revenue
    # print("Objective Function:" + str(func_objective))
    transactions = {}
    transactions['shared_vehicle'] = payment_engine['shared_vehicle'].get_transactions()
    transactions['ride_hailing'] = payment_engine['ride_hailing'].get_transactions()
    if store_results:
        transactions['shared_vehicle'].to_csv(Path(output_folder, transaction_file + 'shared_vehicle'), index=False)
        transactions['ride_hailing'].to_csv(Path(output_folder, transaction_file + 'ride_hailing'), index=False)

    # print(DemandFactory.counter)

    if returnDataFrame:
        # Persist Results
        result = {
            # TODO: specify for ride_hailing
            "n_cars_shared_vehicle_fleet": [n_cars],
            "n_scooter_shared_vehicle_fleet": [n_scooter],
            "n_kick_scooter_shared_vehicle_fleet": [n_kick_scooter],
            "n_cars_ride_hailing_fleet": [n_cars],
            "subs_bandwidth": [substitution],
            "price_sensitive_pop_prob": [price_sensitive_pop_prob],
            "seed": [seed],
            "total_revenue_shared_vehicle": [payment_engine['shared_vehicle'].total_revenue],
            "total_revenue_ride_hailing": [payment_engine['ride_hailing'].total_revenue],
            "total_cost_per_day_shared_vehicle": [total_cost_per_day['shared_vehicle']],
            "total_cost_per_day_ride_hailing": [total_cost_per_day['ride_hailing']],
            "total_profit_shared_vehicle": [
                payment_engine['shared_vehicle'].total_revenue - total_cost_per_day['shared_vehicle']],
            "total_profit_ride_hailing": [
                payment_engine['ride_hailing'].total_revenue - total_cost_per_day['ride_hailing']],
            "total_fulfilled_trips_shared_vehicle": [payment_engine['shared_vehicle'].total_fulfilled_trips],
            "total_fulfilled_trips_ride_hailing": [payment_engine['ride_hailing'].total_fulfilled_trips],
            "total_missed_trips_shared_vehicle": [payment_engine['shared_vehicle'].total_missed_trips],
            "total_missed_trips_ride_hailing": [payment_engine['ride_hailing'].total_missed_trips],
            "total_missed_revenue_shared_vehicle": [payment_engine['shared_vehicle'].total_missed_revenue],
            "total_missed_revenue_ride_hailing": [payment_engine['ride_hailing'].total_missed_revenue],
            "vehicles_to_be_charged_shared_vehicle": [no_vehicles_to_be_charged['shared_vehicle']],
            "vehicles_to_be_charged_ride_hailing": [no_vehicles_to_be_charged['ride_hailing']]
        }

        # Calculate performance indicators per mode
        indicators_per_mode = transactions[transactions["selected_vehicle_mode"] != 'None'].groupby(
            ["selected_vehicle_mode"]).agg(
            {"price": "sum", "duration": "sum", "distance": "sum", "energy_consumption": "sum"})

        # Count Trips by Vehicle Type
        overall_rentals = pd.DataFrame(result)
        for mode in available_vehicle_modes:
            rentals = transactions[transactions["selected_vehicle_mode"] == mode].groupby("state").agg(
                {"SharedCar": "sum", "SharedScooter": "sum", "SharedKickScooter": "sum"}).reset_index(drop=True)
            rentals = rentals.add_prefix('{}_'.format(mode))
            overall_rentals = pd.concat([overall_rentals, rentals], axis=1)

            # Prepare KPI per Mode (Distance, Duration, Revenue)
            kpi_for_mode = indicators_per_mode.loc[[mode]].reset_index(drop=True)
            kpi_for_mode.rename(columns={"price": "revenue"}, inplace=True)  # to avoid future confusion
            kpi_for_mode = kpi_for_mode.add_prefix('{}_'.format(mode))
            overall_rentals = pd.concat([overall_rentals, kpi_for_mode], axis=1)

        return overall_rentals
    else:
        return (payment_engine['shared_vehicle'].total_revenue, payment_engine['ride_hailing'].total_revenue,
                total_cost_per_day['shared_vehicle'], total_cost_per_day['ride_hailing'],
                payment_engine['shared_vehicle'].total_revenue - total_cost_per_day['shared_vehicle'],
                payment_engine['ride_hailing'].total_revenue - total_cost_per_day['shared_vehicle'],
                payment_engine['shared_vehicle'].total_fulfilled_trips,
                payment_engine['ride_hailing'].total_fulfilled_trips,
                payment_engine['shared_vehicle'].total_missed_trips,
                payment_engine['ride_hailing'].total_missed_trips,
                payment_engine['shared_vehicle'].total_missed_revenue,
                payment_engine['ride_hailing'].total_missed_revenue,
                no_vehicles_to_be_charged['shared_vehicle'],
                no_vehicles_to_be_charged['ride_hailing'],
                func_objective['shared_vehicle'], func_objective['ride_hailing'])


a = run_single_simulation(end_time= 2*1400, n_cars=400, n_scooter=0, n_kick_scooter=0, seed=42, substitution=0.1)
print(a)

# Random Variables for our Monte Carlo Run
# import random
# random.seed(42)
# seeds = random.sample(range(10000), 100)
#
# # Store all simulation results in this data frame
# all_simulations = pd.DataFrame()
#
#
# # End Time
# T = 1440
#
# # Real Run
# pop_probs = [0.0, 1.0]
# sub_bandwidths = [0.0, 0.05, 0.1, 0.2]
#
# for idx, seed in enumerate(seeds):
#     for pop_prob in pop_probs:
#         for sub_bandwidth in sub_bandwidths:
#             sim_res = run_single_simulation(end_time = T, n_cars = 1500, n_scooter = 1500, n_kick_scooter = 1500, seed = seed, substitution = sub_bandwidth, price_sensitive_pop_prob = pop_prob, returnDataFrame = True)
#             all_simulations = pd.concat([all_simulations, sim_res], axis = 0)
#             logging.warning("seed: {}, idx: {}, pop_prob: {}, sub: {}".format(seed, idx, pop_prob, sub_bandwidth),extra={"clazz": "main", "oid": ""})
#
#     # After each seed save
#     all_simulations.to_csv('all_simulation_results.csv')
#
# print("FINISHED")
