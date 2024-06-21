##### This is a template for a sharedvehicle fleet consisting of shared cars, schared scooters and shared kickscooters. Shared bikes are not yet added ########

##Imports
# Standard library imports
import os
import sys
from enum import Enum
from pathlib import Path
from configparser import ConfigParser
import logging
import time
import matplotlib.pyplot as plt

# Third-party library imports
import simpy
import pandas as pd
import numpy as np

from simulation.operator.operations_management.integrated_shared_mobility_operations import \
    IntegratedSharedMobilityOperations
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
from simulation.vehicle.shared_bike import SharedBike
from simulation.vehicle.shared_vehicle import SharedVehicle
from simulation.vehicle_choice_model.distance_based_shared_vehicle_choice_behavior import \
    DistanceBasedSharedVehicleVehicleChoiceBehavior

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
    SharedVehicleConfig,
    SharedVehicleOperatorConfig,
    ChargingInfrastructureConfig,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import vehicle types and vehicle choice options
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import (
    OnlyCarVehicleChoiceBehavior,
)

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)

# Import operator related modules
from simulation.operator.fleet_factory import (
    generate_mixed_fleet,
    generate_fleet_config,
)
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.operator.operations_management.relocation_scheduler import (
    RelocationScheduler,
)
from simulation.operator.operations_management.task_queue import TaskQueue

# Import metrics
from simulation.metrics.metrics_factory import MetricsFactory

import random
from deap import base, creator, tools, algorithms

from optimization.DistributionOptimizer import DistributionOptimizer

# Change working directory to path of this file
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])


class SimulationStrategy(Enum):
    MIN_CO2 = 0
    MAX_REVENUE = 1
    MIN_TRAVEL_TIME = 2
    CONV_FULFILLMENT_RATE = 3


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


def run_simulation(n_cars, n_scooters, n_kick_scooters, n_bikes, strategy, rn, df_metrics):
    print(
        f'Gen: {rn._gen} Sim: {rn._num} num vehicles: cars: {n_cars}, scooters: {n_scooters}, kick_scooters: {n_kick_scooters}, bikes: {n_bikes}, Sum: {(n_cars + n_scooters + n_kick_scooters + n_bikes)}')

    start_time = time.time()

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Basic Configuration                     #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    seed = None

    # World / Resolution Config
    spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
    temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
    daily_res = parser.getint("WORLD", "daily_resolution")
    city = parser.get("WORLD", "city")

    # Create Global Config File
    global_config = Configuration.init(spatial_res, temporal_res, daily_res, city=city)

    # Input Files (Demand)
    demand_file_path = parser.get("DEMAND", "path_trip_demand").format(city=city)
    demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

    # Input Files (Supply)
    supply_file_path = parser.get("SUPPLY", "path_vehicle_supply").format(city=city)
    # Get the supply probability from supply file
    supply_prob = pd.read_csv(supply_file_path)

    # Environment files
    bounding_box_path = parser.get("ENVIRONMENT", "path_env_bounding_box")
    env_layer_hex_7 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_7")
    env_layer_hex_8 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_8")
    env_layer_hex_9 = parser.get("ENVIRONMENT", "path_env_hex_layer_res_9")

    # User and Mode Choice Configuration
    # TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/49
    # Check the configuration file before running this, this mode needs only one probability which is the probability of a user being price sensitive or not. Other modes might require multiple inputs.
    pop_prob_sharedvehicle = parser.get(
        "SHARED_VEHICLE_OPERATOR", "population_probabilities"
    ).split(",")
    pop_prob_sharedvehicle = [float(x) for x in pop_prob_sharedvehicle]

    mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
    mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
    mode_choice_sub_boundary = parser.getfloat("MODE_CHOICE_MODEL", "substitution_boundary")

    mc = ModeChoiceConfig(
        mode_choice_strategy, mode_choice_sub_boundary, mode_choice_model_path
    )

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Shared Vehicle Fleet Configuration      #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Read Shared Vehicle Config and add to Global Config File
    # TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/46
    # TODO: SharedScooters and SharedKickScooters do not have an initial state of charge. They start with the max state of charge.
    for idx, vehicle_type in enumerate(
            ["SHARED_BIKE", "SHARED_CAR", "SHARED_SCOOTER", "SHARED_KICK_SCOOTER"]
    ):  # TODO: Can't we get a list from the Config dynamically?
        vehicle_type_classes = [
            "SharedBike",
            "SharedCar",
            "SharedScooter",
            "SharedKickScooter",
        ]
        price_per_min = parser.getfloat(vehicle_type, "PRICE_PER_MIN")
        unlock_fee = parser.getfloat(vehicle_type, "UNLOCK_FEE")
        max_state_of_charge = parser.getfloat(vehicle_type, "MAX_STATE_OF_CHARGE")
        energy_consumption = parser.getfloat(vehicle_type, "ENERGY_CONSUMPTION")
        velocity = parser.getfloat(vehicle_type, "VELOCITY")
        max_available_seats = parser.getint(vehicle_type, "MAX_AVAILABLE_SEATS")
        max_walking_distance = parser.getint(vehicle_type, "WALKING_DISTANCE")
        daily_total_cost = parser.getfloat(vehicle_type, "DAILY_TOTAL_COST")

        initial_SoC = parser.getfloat(vehicle_type, "INITIAL_SOC", fallback=None)

        EV_relative_energy_consumption = parser.getfloat(
            vehicle_type, "EV_RELATIVE_ENERGY_CONSUMPTION", fallback=None
        )
        cost_per_km = parser.getfloat(vehicle_type, "COST_PER_KM", fallback=None)
        charging_cost_per_kWh = parser.getfloat(
            vehicle_type, "CHARGING_COST_PER_KWH", fallback=None
        )
        co2_per_km = parser.getfloat(vehicle_type, "KG_CO2_PER_KM", fallback=None)

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
            co2_per_km,
            unlock_fee
        )
        global_config.add_shared_vehicle_config(vehicle_type_classes[idx], vc)

    # Check the configuration file before running this, different modes might require multiple inputs
    # Vehicles whose state of charge is below the threshold value are to be charged
    recharge_threshold = (
            parser.getfloat("SHARED_VEHICLE_OPERATOR", "RECHARGE_THRESHOLD") / 100
    )
    charging_station_power = parser.getfloat(
        "SHARED_VEHICLE_OPERATOR", "CHARGING_STATION_POWER"
    )
    number_of_service_workers = parser.getint(
        "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_SERVICE_WORKER"
    )
    number_of_base_regions = parser.getint(
        "SHARED_VEHICLE_OPERATOR", "NUMBER_OF_BASE_REGIONS"
    )
    # Hexagons as base regions for service workers to operate
    base_regions = parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
    base_regions = base_regions.split(",")[:number_of_base_regions]

    base_capacity = parser.getint("SHARED_VEHICLE_OPERATOR", "BASE_CAPACITY")
    operations_start = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_START")
    operations_duration = parser.getint("SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION")
    vehicle_relocation_velocity = parser.getint(
        "SHARED_VEHICLE_OPERATOR", "VEHICLE_RELOCATION_VELOCITY"
    )

    available_modes = parser.get(
        "SHARED_VEHICLE_OPERATOR", "available_vehicle_modes_shared_vehicle"
    )
    available_modes = available_modes.split(",")
    available_modes_supply = [n_cars, n_scooters, n_kick_scooters, n_bikes]

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
        n_kick_scooters,
        n_bikes,
    )

    # Vehicle Choice Model
    if mode_choice_strategy == "substitution":
        vehicle_choice_model = DistanceBasedSharedVehicleVehicleChoiceBehavior(
            mode_choice_model_path, mode_choice_sub_boundary, available_modes
        )
    else:
        raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

    # Register all configurations
    global_config.add_mode_choice_config(mc)
    global_config.add_shared_vehicle_operator_config(svoc)

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
    population_factory = PopulationFactory(pop_prob_sharedvehicle, seed)

    # Load Spatial Environment and the environment files
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
    dmi = DistanceMatrixImporter(hexagons, spatial_res, "./data/infrastructure", city=city)
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
    # Output Configuration                    #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

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
    # Init. Simulation Modules.               #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Search Engine finds transportation alternatives for users and manages payment processes
    search_engine = SharedVehicleSearchEngine(env)

    # Vehicle Assignment Engine assigns users to vehicles and notifies them about the pickup position
    vehicle_assignment_engine = SharedVehicleAllocationEngine(env)

    # Configure and generate / spawn shared fleet vehicles
    shared_vehicle_fleet_config = generate_fleet_config(
        supply_prob,
        n_cars=global_config.shared_vehicle_operator_config.n_cars,
        n_scooter=global_config._shared_vehicle_operator_config.n_scooters,
        n_kick_scooter=global_config.shared_vehicle_operator_config.n_kickscooters,
        n_bikes=global_config.shared_vehicle_operator_config.n_bikes,
    )
    mixed_fleet = generate_mixed_fleet(env, shared_vehicle_fleet_config)

    # Add the fleet to the search engine
    search_engine.register_fleet(mixed_fleet)

    # Init Operations Module

    operations = IntegratedSharedMobilityOperations(
        env=env,
        time_between_operations=global_config.shared_vehicle_operator_config.operations_start,
        operation_duration=global_config.shared_vehicle_operator_config.operations_duration,
        distance_matrix=distance_matrix,
        ordered_available_vehicle_modes=available_modes,
        ordered_max_vehicle_supply=available_modes_supply,
        state_of_charge_threshold=global_config.shared_vehicle_operator_config.recharge_threshold,
        base_regions=global_config.shared_vehicle_operator_config.base_regions,
        base_capacity=global_config.shared_vehicle_operator_config.base_capacity,
    )

    # Init operator
    operator = SharedMobilityOperator(
        env=env,
        fleet=mixed_fleet,
        charging_infrastructure=None,
        operations=operations,
        search_engine=search_engine,
        allocation_engine=vehicle_assignment_engine,
        number_service_workers=number_of_service_workers,
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
    # TODO: we need to have a look at https://github.com/IS3UniCologne/urban-mobility-simulation/issues/32
    demand_factory = DemandFactory(
        env, demand_profile, di, world, [], seed, mode="shared_vehicle"
    )
    env.process(demand_factory.generate_demand())

    # Start the operations of the shared operator
    env.process(operations.execute())

    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    # Run the simulation until end time
    env.run(until=30)

    logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})

    transactions = operator.get_transactions()
    transactions.to_excel(f'data/output/simulation_logs/progress/tran_c_{n_cars}_s_{n_scooters}_ks_{n_kick_scooters}_b_{n_bikes}.xlsx', index=False)

    metrics_factory = MetricsFactory(transactions)

    num_vehicles = {
        "SharedBike": n_bikes,
        "SharedCar": n_cars,
        "SharedKickScooter": n_kick_scooters,
        "SharedScooter": n_scooters,
    }

    general_metrics = metrics_factory.general_metrics
    society_metrics = metrics_factory.society_metrics
    service_provider_metrics = metrics_factory.service_provider_metrics
    customer_metrics = metrics_factory.customer_metrics

    print(f'Co2: {society_metrics.get_co2_emissions(global_config.get_co2_per_vehicle_km()).sum()}')
    print(f'Revenue: {service_provider_metrics.get_revenue()}')
    rn.increase()

    print('Ful rate: ', general_metrics.get_fulfillment_rate())

    end_time = time.time()

    execution_time = end_time - start_time
    print(f"Execution time: {execution_time / 60} min")

    metrics = {
        "gen": rn._gen,
        "num_ful_trips": general_metrics.get_num_fulfilled_trips(),
        "num_miss_trips": general_metrics.get_num_missed_trips(),
        "ful_rate": general_metrics.get_fulfillment_rate(),
        "distance": general_metrics.get_traveled_distance(),
        "co2_emissions": society_metrics.get_co2_emissions(global_config.get_co2_per_vehicle_km()).sum(),
        "avg_fleet_util": service_provider_metrics.get_avg_fleet_utilization(num_vehicles),
        "fleet_revenue": service_provider_metrics.get_revenue(),
        "travel_time": customer_metrics.get_travel_time(),
        "wait_time": customer_metrics.get_avg_waiting_time(),
        "costs": customer_metrics.get_cost(),
        "n_cars": n_cars,
        "n_scooters": n_scooters,
        "n_kick_scooters": n_kick_scooters,
        "n_bikes": n_bikes,
        "exec_time": execution_time,
        "planned_charging_tasks": operations.planned_charging_tasks,
        "planned_relocation_task": operations.planned_relocation_task
    }

    df_metrics.loc[len(df_metrics)] = metrics

    # return society_metrics.get_co2_emissions(global_config.get_co2_per_vehicle_km()).sum()

    fulfillment_rate = general_metrics.get_fulfillment_rate()

    # Penalty
    if fulfillment_rate < 0.8:
        if strategy == SimulationStrategy.MIN_CO2:
            return (1 - fulfillment_rate) * society_metrics.get_co2_emissions(
                global_config.get_co2_per_vehicle_km()).sum()
        elif strategy == SimulationStrategy.MAX_REVENUE:
            return fulfillment_rate * service_provider_metrics.get_revenue()
        elif strategy == SimulationStrategy.MIN_TRAVEL_TIME:
            return (1 - fulfillment_rate) * customer_metrics.get_travel_time()

    if strategy == SimulationStrategy.MIN_CO2:
        return society_metrics.get_co2_emissions(global_config.get_co2_per_vehicle_km()).sum()
    elif strategy == SimulationStrategy.MAX_REVENUE:
        return service_provider_metrics.get_revenue()
    elif strategy == SimulationStrategy.MIN_TRAVEL_TIME:
        return customer_metrics.get_travel_time()
    elif strategy == SimulationStrategy.CONV_FULFILLMENT_RATE:
        return fulfillment_rate
    return metrics_factory


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Simulation                        #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


class RefNum:
    _num = 1
    _gen = 0

    def increase(self):
        self._num = self._num + 1

    def increase_gen(self):
        self._gen = self._gen + 1


rn = RefNum()

columns = [
    "gen", "num_ful_trips", "num_miss_trips", "ful_rate", "distance", "co2_emissions",
    "avg_fleet_util", "fleet_revenue", "travel_time", "wait_time", "costs", "n_cars",
    "n_scooters",
    "n_kick_scooters",
    "n_bikes", "exec_time", "planned_charging_tasks", "planned_relocation_task"
]
df_metrics = pd.DataFrame(columns=columns)


def fleet_fulfillment_rate_convergence():
    n_cars = 500
    n_scooters = 200
    n_kick_scooters = 500
    n_bikes = 800

    UPPER_BORDER = 1
    i = 0
    fulfillment_rate = 0.0
    all_rates = []

    while fulfillment_rate <= 100 and i < UPPER_BORDER:
        fulfillment_rate = run_simulation(n_cars, n_scooters, n_kick_scooters, n_bikes,
                                          SimulationStrategy.CONV_FULFILLMENT_RATE, rn, df_metrics)
        all_rates.append(fulfillment_rate)
        print(f'Fulfillment rate of Simulation: {rn._num} with {n_cars} Vehicles is: {fulfillment_rate}')

        n_cars += 150
        n_scooters += 150
        n_kick_scooters += 150
        n_bikes += 150
        i += 1

    # Creating the plot
    plt.figure(figsize=(10, 6))
    plt.plot(range(len(all_rates)), all_rates, marker='o')

    # Adding titles and labels
    plt.title('Fulfillment Rate Over Time')
    plt.xlabel('t')
    plt.ylabel('Fulfillment Rate')

    # Displaying the plot
    plt.savefig('fulfillment_rate_plot.png')



def minimize_co2(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual
    gen = 0
    return run_simulation(n_cars, n_scooters, n_kick_scooters, n_bikes, SimulationStrategy.MIN_CO2, rn, df_metrics),


def maximize_revenue(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual
    res = run_simulation(n_cars, n_scooters, n_kick_scooters, n_bikes, SimulationStrategy.MAX_REVENUE, rn, df_metrics),

    print(f'Simulation Res: {res}')

    return res


def minimize_travel_time(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual
    gen = 0
    return run_simulation(n_cars, n_scooters, n_kick_scooters, n_bikes, SimulationStrategy.MIN_TRAVEL_TIME, rn,
                          df_metrics),
if __name__ == '__main__':
    dis_optimizer = DistributionOptimizer(3500, is_maximization=True)
    dis_optimizer.build(maximize_revenue)
    dis_optimizer.optimize(2, 3, rn)
    df_metrics.to_excel('./sim_metrics.xlsx')

#fleet_fulfillment_rate_convergence()

sys.exit()
# TODO: In the end filter the sim_metrics though the hall of fame, but keep the distributions that the algorithm tested
# to analyze the space the algorizhm searched for
df_metrics.to_excel('./sim_metrics.xlsx')
sys.exit()
dis_optimizer.build(maximize_revenue)
df_metrics.to_excel('./sim_metrics.xlsx')
