from pathlib import Path
import random
import pandas as pd
from pqdm.processes import pqdm
import multiprocessing as mp
import numpy as np
from simulation.agent.user import User  # must come before DemandFactory, otherwise circular imports
from simulation.helper.configuration.configuration import Configuration, VehicleConfig, ModeChoiceConfig, \
    SharedVehicleOperatorConfig, ChargingInfrastructureConfig
from simulation.infrastructure.charging_stations.charging_infastructure import ChargingInfrastructure
from simulation.infrastructure.helper.distance_matrix_importer import DistanceMatrixImporter
from simulation.operator.fleet_factory import generate_mixed_ride_hailing_fleet, generate_ridehailing_fleet_config
from simulation.operator.operations_management.operations_ridehailing import OperationsRidehailing
from simulation.operator.operations_management.rebalancing_scheduler_ridehailing import RebalancingSchedulerRidehailing
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.operator.ride_hailing_allocation_engine import RideHailingAllocationEngine
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import OnlyCarVehicleChoiceBehavior
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.demand.demand_importer import DemandImporter
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
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
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
for idx, vehicle_type in enumerate(["SHARED_CAR"]):
    vehicle_type_classes = ["SharedCar"]
    price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
    max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
    energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
    velocity = parser.getfloat(vehicle_type, "VELOCITY")
    max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
    max_walking_distance = parser.getint(vehicle_type, "WALKING_DISTANCE")
    daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")
    initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC")

    vc = VehicleConfig(price_per_min, max_state_of_charge, energy_consumption, velocity, max_available_seats,
                       max_walking_distance, daily_total_cost, initial_SoC)
    global_config.add_vehicle_config(vehicle_type_classes[idx], vc)

# Read EV penetration for RideHailingCars
EV_penetration = parser.getfloat('SUPPLY', "EV_penetration")
AV_penetration = parser.getfloat('SUPPLY', "AV_penetration")

# Read ride-hailing related parameters
driver_payment_share = parser.getfloat('RIDE_HAILING', "DRIVER_PAYMENT_SHARE")
global_config.add_ride_hailing_info(driver_payment_share)

# Read Mode Choice Configuration
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")
mode_choice_available_modes = parser.get("MODE_CHOICE_MODEL", "available_modes")
mode_choice_available_modes = mode_choice_available_modes.split(',')
AV_trust = parser.get("MODE_CHOICE_MODEL", "AV_trust").split(',')
AV_trust = [float(x) for x in AV_trust]

mc = ModeChoiceConfig(mode_choice_strategy, mode_choice_sub_boundary, mode_choice_available_modes,
                      mode_choice_model_path)
global_config.add_mode_choice_config(mc)

# Read Shared Vehicle Operator Config
# recharge_threshold = parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD")
recharge_threshold = parser.get("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD").split(',')
recharge_threshold = [float(x) / 100 for x in recharge_threshold]
global_config.add_recharging_threshold(recharge_threshold)

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

# Output Configuration
store_results = parser.getboolean("OUTPUT", "persist_results")
store_results = parser.getboolean("OUTPUT", "persist_results")
output_folder = parser.get("OUTPUT", "output_folder")
transaction_file = parser.get("OUTPUT", "transaction_file")
fleet_state_file = parser.get("OUTPUT", "fleet_state_file")

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
cf_init = SimulationContextFilter(filter_name='add_env', extra=[])
logger.addFilter(cf_init)
# logger.addHandler(file_handler)


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
        env_df_hex_9 = gpd.read_file(file, driver="GeoJSON")
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


def run_single_simulation(start_time=0, end_time=20, n_cars=500, seed=42, phase=1, AV_trust=AV_trust,
                          pop_prob=0.0, allocation=None, EV_penetration=1.0, AV_penetration=1, returnDataFrame=False,
                          charging_capacity=20, charging_power=50):
    """
    :param start_time:
    :param end_time:
    :param n_cars:
    :param n_scooter:
    :param n_kick_scooter:
    :param seed:
    :param substitution:
    :param pop_prob: 1.0 means only price sensitive users, 0.0 means only sustainable users
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
    ### Technology penetration
    global_config.add_tech_penetration(EV_penetration, AV_penetration)
    global_config.add_AV_trust(AV_trust)

    # Read drivers availability distribution
    drivers_availability = parser.get('SUPPLY', "RH_availability").split(',')
    drivers_availability = [round(float(x) * n_cars * (1 - AV_penetration)) for x in drivers_availability]
    global_config.add_driver_availability_vector(drivers_availability)

    # Vehicle Choice Model
    if mode_choice_strategy == "substitution":
        vehicle_choice_model = OnlyCarVehicleChoiceBehavior(['RideHailingCar', 'AutonomousCar'])

    else:
        raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

    # Population Type
    population_factory = PopulationFactory(pop_prob, seed)

    # Charging Infrastructure
    charging_location_list = parser.get("Charging_Infrastructure", "BASE_REGIONS").split(',')
    ### Activate it if there are specific capacity for charging stations
    # charging_power_list = parser.get("Charging_Infrastructure", "CHARGING_STATION_POWER").split(',')
    # charging_power_list = [float(x) for x in charging_power_list]
    # charging_capacity_list = parser.get("Charging_Infrastructure", "CHARGING_STATION_CAPACITY").split(',')
    # charging_capacity_list = [float(x) for x in charging_capacity_list]
    charging_power_list = list(np.zeros(len(charging_location_list)) + charging_power)
    charging_capacity_list = list(np.zeros(len(charging_location_list)) + charging_capacity)
    sic = ChargingInfrastructureConfig(charging_location_list, charging_power_list, charging_capacity_list)
    global_config.add_charging_infrastructure_config(sic)
    charging_infrastructure = ChargingInfrastructure(env, charging_location_list, charging_power_list,
                                                     charging_capacity_list, reset=True)

    # World
    world = World.init(env, search_engine, search_engine, vehicle_assignment_engine, vehicle_choice_model,
                       population_factory, charging_infrastructure, reset=True)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Spawn Demand Processes.                 #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    ride_hailing_demand_factory = DemandFactory(env, demand_profile, di, world, demand_modifier_paths, seed,
                                                mode='ride_hailing')

    env.process(ride_hailing_demand_factory.generate_demand())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Load Vehicle Fleet and Place on World.  #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    supply_prob = pd.read_csv(supply_file_path)

    ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(distribution=supply_prob, n_cars=n_cars,
                                                                    n_AVs=n_cars, allocation_method='historical',
                                                                    allocation=allocation)
    ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(env, ride_hailing_fleet_config_0)
    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Inject Modules.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    search_engine['ride_hailing'].register_fleet(ride_hailing_fleet_0)

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Operations Management Processes         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    available_vehicle_modes_ridehailing = ['RideHailingCar', 'AutonomousCar']
    available_vehicle_modes_supply_ride_hailing = [n_cars, n_cars]
    no_service_workers = global_config.shared_vehicle_operator_config.number_of_service_worker
    base_regions = global_config.shared_vehicle_operator_config.base_regions
    base_capacity = global_config.shared_vehicle_operator_config.base_capacity

    # Initialize Rule Based Relocation Scheduler

    # For RideHailing Fleets
    rs_ridehailing = RebalancingSchedulerRidehailing(distance_matrix, ride_hailing_fleet_0,
                                                     available_vehicle_modes_ridehailing,
                                                     available_vehicle_modes_supply_ride_hailing, no_service_workers,
                                                     base_regions, base_capacity, recharge_threshold,
                                                     charging_infrastructure._chargers)

    # Store Tasks which are processed by service workers
    task_queue_ridehailing = TaskQueue(env)

    # Init Operations Module

    ops_ridehailing = OperationsRidehailing(env, ride_hailing_fleet_0,
                                            global_config.shared_vehicle_operator_config.operations_start,
                                            global_config.shared_vehicle_operator_config.operations_duration,
                                            rs_ridehailing,
                                            payment_engine['ride_hailing'], available_vehicle_modes_ridehailing,
                                            available_vehicle_modes_supply_ride_hailing,
                                            global_config.shared_vehicle_operator_config.recharge_threshold,
                                            task_queue_ridehailing, charging_infrastructure._chargers)

    env.process(ops_ridehailing.timer())
    env.process(ops_ridehailing.run_operations())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Run Simulation.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    logging.warning(f"Starting Simulation.",
                    extra={"clazz": "main", "oid": ""})

    env.run(until=end_time)

    logging.warning(f"Simulation Finished.",
                    extra={"clazz": "main", "oid": ""})

    total_cost_per_day = {'ride_hailing': (global_config.get_vehicle_config(
        "SharedCar").daily_total_cost * AV_penetration * n_cars) * (end_time / 1440)}

    # Daily Total Cost (CAPEX+OPEX) (cost derived from RevCalc excel in iCloud folder)
    no_vehicles_to_be_charged = {'ride_hailing': ride_hailing_fleet_0.get_all_vehicles_below_soc_level(
        global_config.shared_vehicle_operator_config.recharge_threshold)}

    total_operational_cost = {'ride_hailing': ride_hailing_fleet_0.get_operational_costs()}

    # Final Objective Function for Heuristic Search
    func_objective = {
        'ride_hailing': payment_engine['ride_hailing'].total_revenue - total_cost_per_day['ride_hailing'] - \
                        payment_engine['ride_hailing'].total_missed_revenue - total_operational_cost[
                            'ride_hailing']}
    transactions = {'ride_hailing': payment_engine['ride_hailing'].get_transactions()}

    if store_results:
        transactions['ride_hailing'].to_csv(
            Path(output_folder, 'ride_hailing_' + scenario_name + '_' + 'phase_' + str(phase) + '_' + transaction_file),
            index=False)

    if returnDataFrame:
        # Persist Results
        result = {

            "fleet_size": [n_cars],
            "charging_capacity": [charging_capacity],
            "charging_power": [charging_power],
            "pop_prob": [pop_prob],
            "AV_trust": [AV_trust],
            "AV_penetration": [AV_penetration],
            "seed": [seed],
            "phase": [phase],
            "total_revenue_ride_hailing": [payment_engine['ride_hailing'].total_revenue],
            "total_cost_per_day_ride_hailing": [total_cost_per_day['ride_hailing']],
            "total_operational_cost_per_day_ride_hailing": total_operational_cost['ride_hailing'],
            "total_profit_ride_hailing": [
                payment_engine['ride_hailing'].total_revenue - total_cost_per_day['ride_hailing'] -
                total_operational_cost['ride_hailing']],
            "total_trips_ride_hailing": len(world.users),
            "total_fulfilled_trips_ride_hailing": [payment_engine['ride_hailing'].total_fulfilled_trips],
            "total_missed_trips_ride_hailing": [payment_engine['ride_hailing'].total_missed_trips],
            "total_missed_revenue_ride_hailing": [payment_engine['ride_hailing'].total_missed_revenue]
        }

        transactions = transactions['ride_hailing']
        # Calculate performance indicators per mode
        indicators_per_mode = transactions[transactions["selected_vehicle_mode"] != 'None'].groupby(
            ["selected_vehicle_mode"]).agg(
            {"price": "sum", "duration": "sum", "distance": "sum", "energy_consumption": "sum",
             "waiting_time": "sum", "pick_up_time": "sum"})

        # Count Trips by Vehicle Type
        overall_rentals = pd.DataFrame(result)
        available_modes = ['RideHailingCar_True', 'RideHailingCar_False', 'AutonomousCar_True']
        for mode in available_modes:
            rentals = transactions[transactions["selected_vehicle_mode"] == mode].groupby("state").agg(
                {"RideHailingCar": "sum", "AutonomousCar": "sum"}).reset_index(drop=True)
            rentals = rentals.add_prefix('{}_'.format(mode))
            overall_rentals = pd.concat([overall_rentals, rentals], axis=1)
            # "RideHailingCar_True": "sum", "RideHailingCar_False": "sum", "AutonomousCar_True": "sum"
            # Prepare KPI per Mode (Distance, Duration, Revenue)
            try:
                kpi_for_mode = indicators_per_mode.loc[[mode]].reset_index(drop=True)
            except:
                kpi_for_mode = pd.DataFrame(
                    pd.Series({"price": 0, "duration": 0, "distance": 0, "energy_consumption": 0,
                               "waiting_time": 0, "pick_up_time": 0})).transpose()
            kpi_for_mode.rename(columns={"price": "revenue"}, inplace=True)  # to avoid future confusion
            kpi_for_mode = kpi_for_mode.add_prefix('{}_'.format(mode))
            overall_rentals = pd.concat([overall_rentals, kpi_for_mode], axis=1)

        return overall_rentals
    else:
        return (payment_engine['ride_hailing'].total_revenue,
                total_cost_per_day['ride_hailing'], total_operational_cost['ride_hailing'],
                payment_engine['ride_hailing'].total_revenue - total_cost_per_day['ride_hailing'] -
                total_operational_cost['ride_hailing'],
                payment_engine['ride_hailing'].total_fulfilled_trips,
                payment_engine['ride_hailing'].total_missed_trips,
                no_vehicles_to_be_charged['ride_hailing'],
                func_objective['ride_hailing'])


TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
USER_SHARES = [0.247, 0.237, 0.19, 0.325]
random.seed(42)
seeds = random.sample(range(1000), 10)
phase = 2
for seed in seeds[1:]:
    a = run_single_simulation(end_time=1400 * 5, n_cars=500, seed=seed, phase=phase,
                              pop_prob=USER_SHARES, EV_penetration=TECH_SHARE[phase], charging_capacity=20,
                              AV_penetration=TECH_SHARE[phase], returnDataFrame=False, charging_power=22)

    print(a)


# Simulation Experiments
# Random Variables for our Monte Carlo Run


random.seed(42)
seeds = random.sample(range(1000), 10)

# Store all simulation results in this data frame
all_simulations = pd.DataFrame()

# scenario_1: [1.0,0.0,0.0,0.0]
# scenario_2: [0.75,0.25,0.0,0.0]
# scenario_3: [0.50,0.50,0.0,0.0]
# scenario_4: [0.25,0.75,0.0,0.0]
# scenario_5: [0.0,1.0,0.0,0.0]
SHARES = [[0.247, 0.237, 0.19, 0.325], [0.247, 0.237, 0.19, 0.325], [0.247, 0.237, 0.19, 0.325],
          [0.247, 0.237, 0.19, 0.325], [0.247, 0.237, 0.19, 0.325], [0.247, 0.237, 0.19, 0.325],
          [0.247, 0.237, 0.19, 0.325], [0.247, 0.237, 0.19, 0.325], [0.247, 0.237, 0.19, 0.325],
          [0.247, 0.237, 0.19, 0.325]]
fleet_size = 500
scenario = 5
sim_days = 1
scenario_name = f'charging_capacity_analysis'  # AV_trust_analysis, population_analysis, fleet_size_analysis, charging_capacity_analysis
USER_SHARES = SHARES[scenario - 1]
TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
phases = [0, 1, 2, 3]

# Real Run

if __name__ == '__main__':
    T = 1440 * sim_days
    ### This is for analysing different proportion of user population
    # for pop_type in range(4):
    #     for user_share in range(11):
    #
    #         POP_PROB = [(10 - user_share) / 3 * 0.1, (10 - user_share) / 3 * 0.1, (10 - user_share) / 3 * 0.1,
    #                     (10 - user_share) / 3 * 0.1]
    #         POP_PROB[pop_type] = user_share * 0.1
    #         for phase in phases:
    #             data = []
    #             for idx, seed in enumerate(seeds):
    #                 data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
    #                              'phase': phase, 'pop_prob': POP_PROB,
    #                              'EV_penetration': TECH_SHARE[phase],
    #                              'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
    #             sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
    #                            mp_context=mp.get_context('spawn'))
    #             for i in range(len(sim_res)):
    #                 all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
    #             logging.error("seed: {}, idx: {}".format(seed, idx),
    #                           extra={"clazz": "main", "oid": ""})
    #
    #             # After each seed save
    #             all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)
    #
    # print("FINISHED")

    ### This is for analysing different AV_trust values
    # POP_PROB = SHARES[0]
    # # for pop_type in range(4):
    # for a_1 in [2, 4, 6, 8]:
    #     for a_2 in [2, 4, 6, 8]:
    #         for a_3 in [2, 4, 6, 8]:
    #             for a_4 in [2, 4, 6, 8]:
    #                 # AV_TRUST = [(10 - av_trust) / 3, (10 - av_trust) / 3, (10 - av_trust) / 3,
    #                 #             (10 - av_trust) / 3]
    #                 # AV_TRUST[pop_type] = av_trust
    #                 AV_TRUST = [a_1, a_2, a_3, a_4]
    #                 for phase in phases:
    #                     data = []
    #                     for idx, seed in enumerate(seeds):
    #                         data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
    #                                      'phase': phase, 'pop_prob': POP_PROB, "AV_trust": AV_TRUST,
    #                                      'EV_penetration': TECH_SHARE[phase],
    #                                      'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
    #                     sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
    #                                    mp_context=mp.get_context('spawn'))
    #                     for i in range(len(sim_res)):
    #                         all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
    #                     logging.error("seed: {}, idx: {}".format(seed, idx),
    #                                   extra={"clazz": "main", "oid": ""})
    #
    #                     # After each seed save
    #                     all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'),
    #                                            index=False)
    #
    # print("FINISHED")

    ### This is for analysing different fleet sizes

    # POP_PROB = SHARES[0]
    # for fleet_size in [200, 300, 400, 500, 600, 700, 800, 1000]:
    #     for phase in phases:
    #         data = []
    #         for idx, seed in enumerate(seeds):
    #             data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
    #                          'phase': phase, 'pop_prob': POP_PROB,
    #                          'EV_penetration': TECH_SHARE[phase],
    #                          'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
    #         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
    #                        mp_context=mp.get_context('spawn'))
    #         for i in range(len(sim_res)):
    #             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
    #         logging.error("seed: {}, idx: {}".format(seed, idx),
    #                       extra={"clazz": "main", "oid": ""})
    #
    #         # After each seed save
    #         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)
    #
    # print("FINISHED")

    ### This is for analysing different charging power
    # fleet_size = 500
    # POP_PROB = SHARES[0]
    # for charging_power in [5, 10, 22, 50]:
    #     for phase in phases:
    #         data = []
    #         for idx, seed in enumerate(seeds):
    #             data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
    #                          'phase': phase, 'pop_prob': POP_PROB,
    #                          'EV_penetration': TECH_SHARE[phase],
    #                          'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True,
    #                          'charging_power': charging_power})
    #         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
    #                        mp_context=mp.get_context('spawn'))
    #         for i in range(len(sim_res)):
    #             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
    #         logging.error("seed: {}, idx: {}".format(seed, idx),
    #                       extra={"clazz": "main", "oid": ""})
    #
    #         # After each seed save
    #         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)
    #
    # print("FINISHED")