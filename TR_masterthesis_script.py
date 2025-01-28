##### This is a template for a sharedvehicle fleet consisting of shared cars, schared scooters and shared kickscooters. Shared bikes are not yet added ########

##Imports
# Standard library imports
import logging
import os
import sys
import time
import traceback
from configparser import ConfigParser
from datetime import datetime
from enum import Enum
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Third-party library imports
import simpy
from statsmodels.iolib.smpickle import load_pickle

from optimization.DistributionOptimizer import DistributionOptimizer

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    Configuration,
    ModeChoiceConfig,
    SharedVehicleConfig,
    SharedVehicleOperatorConfig,
)
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter

# Import infrastructure related modules
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)

# Import metrics
from simulation.metrics.metrics_factory import MetricsFactory

# Import operator related modules
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

# Custom module imports
from utils import load_environment

# Change working directory to path of this file
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

checkpoint = None
recovery_path = None

now = datetime.now()
current_sim_id = "sim_" + now.strftime("%d_%m_%H:%M")
os.makedirs("data/output/simulation_logs/" + current_sim_id, exist_ok=True)

if len(sys.argv) == 3:
    checkpoint = sys.argv[2]

if len(sys.argv) == 4:
    if sys.argv[2] != "None":
        checkpoint = sys.argv[2]
    recovery_path = sys.argv[3]


class SimulationStrategy(Enum):
    MIN_CO2 = 0
    MAX_REVENUE = 1
    MIN_TRAVEL_TIME = 2
    CONV_FULFILLMENT_RATE = 3
    PARETO_OPTIMAL = 4
    MAX_FULFILLMENT = 5


# World / Resolution Config
spatial_res = parser.getint("WORLD", "SPATIAL_RESOLUTION")
temporal_res = parser.getint("WORLD", "TEMPORAL_RESOLUTION")
daily_res = parser.getint("WORLD", "daily_resolution")
city = parser.get("WORLD", "city")

# Create Global Config File
global_config = Configuration.init(spatial_res, temporal_res, daily_res, city=city)

# Load Spatial Environment and the environment files
load_environment(city)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Demand Data (once).                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Input Files (Demand)
demand_file_path = parser.get("DEMAND", "path_trip_demand").format(city=city)
demand_modifier_paths = parser.get("DEMAND", "path_demand_modifiers").split(",")

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

# Input Files (Demand)
mode_choice_model_path = parser.get("MODE_CHOICE_MODEL", "path_to_mode_choice_model")
choice_model = load_pickle(mode_choice_model_path)


def run_simulation(
    n_cars, n_scooters, n_kick_scooters, n_bikes, strategy, df_metrics, gen
):
    try:
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
            filename=f'{"data/output/simulation_logs/" + current_sim_id}/tran_c_{n_cars}_s_{n_scooters}_ks_{n_kick_scooters}_b_{n_bikes}.log',
            format="%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s",
            datefmt="%m/%d/%Y %I:%M:%S %p",
        )

        logger = logging.getLogger()
        logger.setLevel(log_level)

        # Add Custom Init Filters (which work without the ENV obj)
        cf = SimulationContextFilter(filter_name="add_env", extra=[])
        logger.addFilter(cf)

        logging.info(
            f"Gen: {gen}num vehicles: cars: {n_cars}, scooters: {n_scooters}, kick_scooters: {n_kick_scooters}, bikes: {n_bikes}, Sum: {(n_cars + n_scooters + n_kick_scooters + n_bikes)}",
            extra={"clazz": "main", "oid": ""},
        )

        start_time = time.time()

        # # # # # # # # # # # # # # # # # # # # # #
        #                                         #
        # Basic Configuration                     #
        #                                         #
        # # # # # # # # # # # # # # # # # # # # # #

        seed = None

        GeodesicEnvironment.getInstance().reset_random_generator(4711)

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

        mode_choice_model_path = parser.get(
            "MODE_CHOICE_MODEL", "path_to_mode_choice_model"
        )
        mode_choice_strategy = parser.get("MODE_CHOICE_MODEL", "mode_choice_strategy")
        mode_choice_sub_boundary = parser.getfloat(
            "MODE_CHOICE_MODEL", "substitution_boundary"
        )

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
                unlock_fee,
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
        operations_duration = parser.getint(
            "SHARED_VEHICLE_OPERATOR", "OPERATIONS_DURATION"
        )
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
                mode_choice_model_path,
                mode_choice_sub_boundary,
                available_modes,
                choice_model,
            )
        else:
            raise NotImplementedError(
                "Other Vehicle Choice Models not Implemented yet."
            )

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
        demand_factory = DemandFactory(
            env, demand_profile, di, world, [], seed, mode="shared_vehicle"
        )
        env.process(demand_factory.generate_demand())

        # Start the operations of the shared operator
        env.process(operations.execute())

        logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

        # Run the simulation until end time
        env.run(until=10080)

        logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})

        transactions = operator.get_transactions()
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

        logging.info(
            f"Co2: {society_metrics.get_co2_emissions(global_config.get_co2_per_vehicle_km()).sum()}",
            extra={"clazz": "main", "oid": ""},
        )
        logging.info(
            f"Revenue: {service_provider_metrics.get_revenue()}",
            extra={"clazz": "main", "oid": ""},
        )

        logging.info(
            f"Ful rate: {general_metrics.get_fulfillment_rate()}",
            extra={"clazz": "main", "oid": ""},
        )

        end_time = time.time()

        execution_time = end_time - start_time
        logging.info(
            f"Execution time: {execution_time / 60} min",
            extra={"clazz": "main", "oid": ""},
        )

        # return society_metrics.get_co2_emissions(global_config.get_co2_per_vehicle_km()).sum()

        fulfillment_rate = general_metrics.get_fulfillment_rate()

        result = None

        # Penalty
        if fulfillment_rate < 0.65:
            if strategy == SimulationStrategy.MIN_CO2:
                result = (
                    np.exp((0.65 - fulfillment_rate) * 20)
                    * society_metrics.get_co2_emissions(
                        global_config.get_co2_per_vehicle_km()
                    ).sum()
                )
            elif strategy == SimulationStrategy.MAX_REVENUE:
                result = (
                    1 / np.exp((0.65 - fulfillment_rate) * 10)
                ) * service_provider_metrics.get_revenue()
            elif strategy == SimulationStrategy.MIN_TRAVEL_TIME:
                result = (
                    np.exp((0.65 - fulfillment_rate) * 10)
                    * customer_metrics.get_travel_time()
                )
            elif strategy == SimulationStrategy.PARETO_OPTIMAL:
                result = (
                    np.exp((0.65 - fulfillment_rate) * 10)
                    * customer_metrics.get_travel_time(),
                    (1 / np.exp((0.65 - fulfillment_rate) * 10))
                    * service_provider_metrics.get_revenue(),
                    np.exp((0.65 - fulfillment_rate) * 10)
                    * society_metrics.get_co2_emissions(
                        global_config.get_co2_per_vehicle_km()
                    ).sum(),
                )

        if result is None:
            # No penalty continue
            if strategy == SimulationStrategy.MIN_CO2:
                result = society_metrics.get_co2_emissions(
                    global_config.get_co2_per_vehicle_km()
                ).sum()
            elif strategy == SimulationStrategy.MAX_REVENUE:
                result = service_provider_metrics.get_revenue()
            elif strategy == SimulationStrategy.MIN_TRAVEL_TIME:
                result = customer_metrics.get_travel_time()
            elif strategy == SimulationStrategy.CONV_FULFILLMENT_RATE:
                result = fulfillment_rate
            elif strategy == SimulationStrategy.PARETO_OPTIMAL:
                result = (
                    customer_metrics.get_travel_time(),
                    service_provider_metrics.get_revenue(),
                    society_metrics.get_co2_emissions(
                        global_config.get_co2_per_vehicle_km()
                    ).sum(),
                )
            elif strategy == SimulationStrategy.MAX_FULFILLMENT:
                result = fulfillment_rate
            else:
                result = metrics_factory

        if type(result) is tuple:
            str_result = "".join(map(str, result)).replace(".", "p")
        else:
            str_result = str(result).replace(".", "p")

        file_path = f"data/output/simulation_logs/{current_sim_id}/gen_{gen}/transactions/tran_c_{n_cars}_s_{n_scooters}_ks_{n_kick_scooters}_b_{n_bikes}_res_{str_result}.csv"
        logging.info(
            f"Worker {current_sim_id}-{gen}: Writing to {file_path}",
            extra={"clazz": "main", "oid": ""},
        )
        transactions.to_csv(file_path, index=False)
        logging.info(
            f"Worker {current_sim_id}-{gen}: Finished writing to {file_path}",
            extra={"clazz": "main", "oid": ""},
        )

        return result
    except Exception as e:
        error_file = f"data/output/simulation_logs/{current_sim_id}/gen_{gen}/error_log_tran_c_{n_cars}_s_{n_scooters}_ks_{n_kick_scooters}_b_{n_bikes}.txt"
        with open(error_file, "w") as f:
            f.write(f"Worker failed with exception: {e}\n")
            f.write(traceback.format_exc())
        logging.error(
            f"Worker {current_sim_id}-{gen} failed with exception: {e}. Logged to {error_file}",
            extra={"clazz": "main", "oid": ""},
        )


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Start Simulation                        #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

columns = [
    "gen",
    "num_ful_trips",
    "num_miss_trips",
    "ful_rate",
    "distance",
    "co2_emissions",
    "avg_fleet_util",
    "fleet_revenue",
    "travel_time",
    "wait_time",
    "costs",
    "n_cars",
    "n_scooters",
    "n_kick_scooters",
    "n_bikes",
    "exec_time",
    "planned_charging_tasks",
    "planned_relocation_task",
    "relative_value",
]
df_metrics = pd.DataFrame(columns=columns)


def fleet_fulfillment_rate_convergence():
    n_cars = 1600
    n_scooters = 1600
    n_kick_scooters = 1600
    n_bikes = 1600

    UPPER_BORDER = 5
    i = 0
    fulfillment_rate = 0.0
    all_rates = []

    while fulfillment_rate <= 100 and i < UPPER_BORDER:
        fulfillment_rate = run_simulation(
            n_cars,
            n_scooters,
            n_kick_scooters,
            n_bikes,
            SimulationStrategy.CONV_FULFILLMENT_RATE,
            df_metrics,
            i,
        )
        all_rates.append(fulfillment_rate)
        print(
            f"Fulfillment rate of Simulation:  with {n_cars} Vehicles is: {fulfillment_rate}"
        )

        n_cars += 100
        n_scooters += 100
        n_kick_scooters += 100
        n_bikes += 100
        i += 1

    # Creating the plot
    plt.figure(figsize=(10, 6))
    plt.plot(range(len(all_rates)), all_rates, marker="o")

    # Adding titles and labels
    plt.title("Fulfillment Rate Over Time")
    plt.xlabel("t")
    plt.ylabel("Fulfillment Rate")

    # Displaying the plot
    plt.savefig("fulfillment_rate_plot.png")
    df_metrics.to_excel("./fulfillment_rate.xlsx")


def minimize_co2(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual[0]
    return (
        run_simulation(
            n_cars,
            n_scooters,
            n_kick_scooters,
            n_bikes,
            SimulationStrategy.MIN_CO2,
            df_metrics,
            individual[1],
        ),
    )


def maximize_revenue(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual[0]
    res = (
        run_simulation(
            n_cars,
            n_scooters,
            n_kick_scooters,
            n_bikes,
            SimulationStrategy.MAX_REVENUE,
            df_metrics,
            individual[1],
        ),
    )
    return res


def minimize_travel_time(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual[0]
    return (
        run_simulation(
            n_cars,
            n_scooters,
            n_kick_scooters,
            n_bikes,
            SimulationStrategy.MIN_TRAVEL_TIME,
            df_metrics,
            individual[1],
        ),
    )


def maximize_fulfillment(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual[0]
    return (
        run_simulation(
            n_cars,
            n_scooters,
            n_kick_scooters,
            n_bikes,
            SimulationStrategy.MAX_FULFILLMENT,
            df_metrics,
            individual[1],
        ),
    )


def pareto_optimality(individual):
    n_cars, n_scooters, n_kick_scooters, n_bikes = individual[0]
    return run_simulation(
        n_cars,
        n_scooters,
        n_kick_scooters,
        n_bikes,
        SimulationStrategy.PARETO_OPTIMAL,
        df_metrics,
        individual[1],
    )


if __name__ == "__main__":
    dis_optimizer = DistributionOptimizer(
        4000,
        is_maximization=False,
        with_multi_processing=True,
        with_pareto_optimal=False,
    )
    dis_optimizer.build(minimize_co2)
    dis_optimizer.optimize(20, 15, current_sim_id, checkpoint, recovery_path)

sys.exit()
