##Imports
# Standard library imports
import logging
import os
import shutil
import sys

# Live Visualization
import threading
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Third-party library imports
import simpy
from matplotlib.animation import FuncAnimation

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    Configuration,
    ModeChoiceStrategy,
)
from simulation.helper.logging.log_manager import LogManager
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
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
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
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking

# Custom module imports
from utils import load_geodesic_environment

# Core metric visualization
from visualization.Data_plots import get_n_users, animate

# Change working directory to path of this file
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Initialize Configuration
config = Configuration()

# make a copy of the used config file that references this run
output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
output_config_dir = os.path.normpath(os.path.join("data", "output", "configs"))
if not os.path.exists(output_config_dir):
    os.makedirs(output_config_dir)
shutil.copy(sys.argv[1], os.path.join(output_config_dir, f"{output_timestamp}.toml"))

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=0)

# Logging
LogManager.setup_logging(config, env)


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Basic Configuration                     #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

mode_choice_strategy = config.mode_choice_model.MODE_CHOICE_STRATEGY
if mode_choice_strategy == ModeChoiceStrategy.SUBSTITUTION_AWARE:
    vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
        ["AutonomousCar", "RideHailingCar"]
    )  ## Needs to be modified depending on the modus
else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### End Basic Configuration #####


# Population Type
# TODO: Generate population for multiple modes at once --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/52
population_factory = PopulationFactory(
    config.population.RIDE_HAILING_POPULATION_PROBABILITIES
)

# Load Spatial Environment

load_geodesic_environment()


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Tracking                          #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

tracking = Tracking.init(env)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Charging Infrastructure                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

charging_infrastructure = ChargingInfrastructure(
    env=env,
    location_list=config.charging_infrastructure.LOCATIONS,
    power_list=config.charging_infrastructure.CHARGING_STATION_POWER,
    capacity_list=config.charging_infrastructure.CHARGING_STATION_CAPACITY,
    queue_size=config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE,
    reset=True,
)

#### End Charging Infrastructure Configuration #####


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(
    f"hex_{config.world.SPATIAL_RESOLUTION_VALUE}"
).index.tolist()
dmi = DistanceMatrixImporter(
    hexagons,
    config.world.SPATIAL_RESOLUTION_VALUE,
    os.path.normpath(os.path.join(".", "data", "infrastructure")),
    config.world.CITY,
)
distance_matrix = dmi.load_distance_matrix()


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
available_vehicle_modes_supply_ride_hailing = [
    config.ride_hailing_global.N_RIDE_HAILING_CARS,
    config.ride_hailing_global.N_AUTONOMOUS_CARS,
]

# Get the supply probability from supply file
supply_prob = pd.read_csv(os.path.normpath(config.path.PATH_VEHICLE_SUPPLY))

ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=config.ride_hailing_global.N_RIDE_HAILING_CARS,
    n_AVs=config.ride_hailing_global.N_AUTONOMOUS_CARS,
)
ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_0
)


ride_hailing_fleet_config_1 = generate_ridehailing_fleet_config(
    distribution=supply_prob,
    n_cars=config.ride_hailing_global.N_RIDE_HAILING_CARS,
    n_AVs=config.ride_hailing_global.N_AUTONOMOUS_CARS,
)
ride_hailing_fleet_1 = generate_mixed_ride_hailing_fleet(
    env, ride_hailing_fleet_config_1
)

# Add the fleet to the search engine
search_engine["ride_hailing_0"].register_fleet(ride_hailing_fleet_0)
search_engine["ride_hailing_1"].register_fleet(ride_hailing_fleet_1)

# Initialize fleet operations

# if queue sizes at charging stations are all zero, we should account for that in the operations
# there can be more clever and nuanced approaches, but as a rule of thumb, we should not allow operations to send vehicles to charging stations that are full if we don't allow queueing
allow_queue = sum(config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE) > 0

ridehailing_operations_0 = RideHailingBaseChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=config.ride_hailing_operators[0].OPERATIONS_START,
    operation_duration=config.ride_hailing_operators[0].OPERATIONS_DURATION,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ride_hailing_operators[0].RECHARGE_THRESHOLD,
    allow_queue=allow_queue,
)

ridehailing_operations_1 = RideHailingBaseChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=config.ride_hailing_operators[0].OPERATIONS_START,
    operation_duration=config.ride_hailing_operators[0].OPERATIONS_DURATION,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ride_hailing_operators[0].RECHARGE_THRESHOLD,
    allow_queue=allow_queue,
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
    env,
    world,
    modifiers=[os.path.normpath(path) for path in config.path.PATH_DEMAND_MODIFIERS],
    mode="ride_hailing",
)
# env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Live Visualization                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# timestamp = []
# y1, y2, y3, y4, y5, y6, y7 = [], [], [], [], [], [], []


# # callback function to get data from world
# def get_n_users() -> list:
#     # fulfilled trips vs. total trips
#     fleet_0_transactions = ridehailing_operator_0.transaction_df
#     fleet_1_transactions = ridehailing_operator_1.transaction_df

#     try:
#         fulfilled_trips_fleet_0 = (
#             fleet_0_transactions["state"].apply(lambda x: "Fulfilled" in x).sum()
#         )
#         fulfilled_trips_fleet_1 = (
#             fleet_1_transactions["state"].apply(lambda x: "Fulfilled" in x).sum()
#         )
#         total_trips_fleet_0 = len(fleet_0_transactions["state"])
#         total_trips_fleet_1 = len(fleet_1_transactions["state"])
#     except Exception:
#         fulfilled_trips_fleet_0 = 0
#         fulfilled_trips_fleet_1 = 0
#         total_trips_fleet_0 = 0
#         total_trips_fleet_1 = 0

#     # global avg station utilization
#     global_station_utilization = 0
#     for charging_station in charging_infrastructure.charging_stations:
#         global_station_utilization += charging_station.plugs.count

#     global_avg_station_utilization = global_station_utilization / len(
#         charging_infrastructure.charging_stations
#     )

#     # add all data to dictionary
#     timestamp.append(env.now)
#     y1.append(len(world.user_processes))
#     y2.append(fulfilled_trips_fleet_0)
#     y3.append(fulfilled_trips_fleet_1)
#     y4.append(total_trips_fleet_0)
#     y5.append(total_trips_fleet_1)
#     y6.append(global_avg_station_utilization)
#     return timestamp, y1, y2, y3, y4, y5, y6


# def animate(i: int, callback: list) -> None:
#     if callback is not None:
#         (
#             timestamp,
#             n_active_users,
#             fulfilled_trips_0,
#             fulfilled_trips_1,
#             total_trips_0,
#             total_trips_1,
#             avg_station_util,
#         ) = callback()

#         # clear whole figure
#         plt.clf()

#         # plot 1
#         plt.subplot(4, 1, 1)
#         plt.plot(timestamp, fulfilled_trips_0, total_trips_0)
#         plt.title("fulfilled vs. total trips (fleet 0)")
#         plt.legend(["fulfilled_trips_0", "total_trips_0"], loc="upper right")

#         # plot 2
#         plt.subplot(4, 1, 2)
#         plt.plot(timestamp, fulfilled_trips_1, total_trips_1)
#         plt.title("fulfilled vs. total trips (fleet 1)")
#         plt.legend(["fulfilled_trips_1", "total_trips_1"], loc="upper right")

#         # plot 3
#         plt.subplot(4, 1, 3)
#         plt.plot(timestamp, n_active_users)
#         plt.title("active users")

#         # plot 4
#         plt.subplot(4, 1, 4)
#         plt.plot(timestamp, avg_station_util)
#         plt.title("global average charging station utilization")

#         plt.tight_layout()


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

# env.run(until=50)

# logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})


# For multiple simulation runs
def run_simulation(end_time, env=env):  # noqa: ANN001, ANN201
    # Before a new simulation run, reset everything
    User.user_id = 0
    DemandFactory.counter = 0

    # Use only if the configuration parameters stay unchanged to avoid reloading everytime. Reload demand factory if the demand profile is different between consecutive runs
    demand_factory.reset()

    env.process(demand_factory.generate_demand())

    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    env.run(until=end_time)

    logging.warning("Ending Simulation.", extra={"clazz": "main", "oid": ""})


# env = simpy.Environment(config.experiment_management.START_TIME)
# run_simulation(end_time=config.experiment_management.END_TIME)

urban_mobility_simulation = threading.Thread(target=run_simulation, args=(1440,))

urban_mobility_simulation.start()

# lists for data
timestamp = []
y1, y2, y3, y4, y5, y6 = [], [], [], [], [], []

# wrap callback function with its arguments
get_data = get_n_users(ridehailing_operator_0, ridehailing_operator_1, charging_infrastructure, world, env, timestamp, y1, y2, y3, y4, y5, y6)

ani = FuncAnimation(
    plt.gcf(),
    animate,
    frames=100,
    interval=1000,
    cache_frame_data=False,
    fargs=(get_data,)

)
plt.show()

run_simulation(end_time=config.experiment_management.END_TIME)
