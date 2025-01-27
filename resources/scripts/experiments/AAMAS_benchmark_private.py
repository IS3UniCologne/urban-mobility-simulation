##Imports
# Standard library imports
import csv
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# Third-party library imports
import simpy

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.config_reader import ConfigReader

# Import configurations and extra logging filters
from simulation.helper.configuration.configuration import (
    Configuration,
    ModeChoiceStrategy,
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
from simulation.operator.operations_management.algorithms.charging_station_allocation import (
    DowntimeMinWithoutLookahead,
)
from simulation.operator.operations_management.ridehailing_MP_charging_operations import (
    RideHailingMPChargingOperations,
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
from utils import load_geodesic_environment

# Change working directory to path of this file
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Initialize an empty Configuration object
config = Configuration.instance()

# Initialize ConfigReader with the configuration file and the Configuration object
config_reader = ConfigReader(sys.argv[1])
config_reader.load_config()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)
logging.getLogger("docplex.util.environment.logger").setLevel(logging.WARNING)

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
    level=config.file_log_level,  # set it to lowest so the handlers can decide
)

# Add Custom Init Filters (which work without the ENV obj)
cf = SimulationContextFilter(filter_name="add_env", extra=[])
logger.addFilter(cf)

consolehandler = logging.StreamHandler()
consolehandler.setLevel(config.log_level)
consolehandler.addFilter(cf)
logger.addHandler(consolehandler)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Basic Configuration                     #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# make a copy of the used config file that references this run
if not os.path.exists("data/output/configs"):
    os.makedirs("data/output/configs")
shutil.copy(sys.argv[1], f"data/output/configs/{output_timestamp}.ini")

if (
    config.get_mode_choice_config().mode_choice_strategy
    == ModeChoiceStrategy.SUBSTITUTION_AWARE
):
    vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
        ["AutonomousCar"]
    )  ## Needs to be modified depending on the modus

else:
    raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

#### Not sure if this part is necessary #####
MoD_interval_reduction = 0  # By choice
config.add_MoD_coefficient_interval_adjuster(MoD_interval_reduction)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Init. Simulation Environment            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

env = simpy.Environment(initial_time=config.start_time)

# Inject Simulation Environment to Logger (such that we can log the env time)
cf = SimulationContextFilter(filter_name="add_env", extra=env)
edf = ExtraDefaultFilter(filter_name="add_default_value")

logger.addFilter(cf)
logger.addFilter(edf)

# Population Type
# TODO: Generate population for multiple modes at once --> https://github.com/IS3UniCologne/urban-mobility-simulation/issues/52
population_factory = PopulationFactory(
    config.ride_hailing_population_probabilities, config.seed
)

# Load Spatial Environment and the environment files
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

# for this scenario, we assume same locations, but split up capacity
separate_charging_capacity_list = [
    c / 2 for c in config.get_charging_infrastructure_config().capacity
]

charging_infrastructure_0 = ChargingInfrastructure(
    env=env,
    location_list=config.get_charging_infrastructure_config().locations,
    power_list=config.get_charging_infrastructure_config().power,
    capacity_list=separate_charging_capacity_list,
    queue_size=config.get_charging_infrastructure_config().queue_size,
    reset=True,
)

charging_infrastructure_1 = ChargingInfrastructure(
    env=env,
    location_list=config.get_charging_infrastructure_config().locations,
    power_list=config.get_charging_infrastructure_config().power,
    capacity_list=separate_charging_capacity_list,
    queue_size=config.get_charging_infrastructure_config().queue_size,
    reset=True,
)

# track charging stations
charging_stations_track_0 = []
charging_stations_track_1 = []


def track_charging_stations(infra, target):
    while True:
        yield env.timeout(1)
        values = [
            {
                "time": env._now,
                "_location": d["_location"],
                "_plugs.count": d["_plugs"].count,
                "_plugs.queuesize": len(d["_plugs"].queue),
            }
            for d in [
                tracking.dump(tracking._get_uid(x))[1] for x in infra.charging_stations
            ]
        ]
        target.extend(values)


env.process(
    track_charging_stations(charging_infrastructure_0, charging_stations_track_0)
)
env.process(
    track_charging_stations(charging_infrastructure_1, charging_stations_track_1)
)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Demand Data (once).                #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

p = Path(config.trip_demand_file)
di = DemandImporter(
    spatial_resolution=config.spatial_resolution,
    temporal_resolution=config.temporal_resolution,
    daily_resolution=config.daily_resolution,
    city=config.city,
)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(
    f"hex_{config.spatial_resolution.value}"
).index.tolist()
dmi = DistanceMatrixImporter(
    hexagons, config.spatial_resolution.value, "./data/infrastructure", config.city
)
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
available_vehicle_modes_supply_ride_hailing = [
    config.ridehailing_operator_config.n_autonomous_cars
]

# Get the supply probability from supply file
supply_prob = pd.read_csv(config.vehicle_supply_file)

ride_hailing_fleet_0 = generate_AV_fleet(
    env, supply_prob, config.ridehailing_operator_config.n_autonomous_cars, seed=4711
)

ride_hailing_fleet_1 = generate_AV_fleet(
    env, supply_prob, config.ridehailing_operator_config.n_autonomous_cars, seed=4711
)

# track vehicles in fleets
vehicles_track = []


def track_fleets(fleet_id):
    # attention: this only works because we do not dynamically create and destroy vehicles like we do with users!
    tracked_list = tracking.list_tracked("RideHailingAV")

    while True:
        yield env.timeout(1)
        envtime, values = (
            env._now,
            {
                "_fleet": fleet_id,
                "_state": [
                    tracking.get(x, "_state")[1]
                    for x in tracked_list
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
                "_current_state_of_charge": [
                    tracking.get(x, "_current_state_of_charge")[1]
                    for x in tracked_list
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
                "_vdt": [
                    tracking.get(x, "_vdt")[1]
                    for x in tracked_list
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
                "_suggested": [
                    tracking.get(x, "_suggested")[1]
                    for x in tracked_list
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

time_minimizing_charging_allocation = DowntimeMinWithoutLookahead()

# Initialize fleet operations
ridehailing_operations_0 = RideHailingMPChargingOperations(
    env=env,
    #    distance_matrix=distance_matrix,
    time_between_operations=config.ridehailing_operator_config.operations_start,
    #    operation_duration=global_config.ridehailing_operator_config.operations_duration,
    #    available_modes=available_vehicle_modes_ridehailing,
    #    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ridehailing_operator_config.recharge_threshold,
    #    allow_queue=False,
    algo=time_minimizing_charging_allocation,
)

ridehailing_operations_1 = RideHailingMPChargingOperations(
    env=env,
    #    distance_matrix=distance_matrix,
    time_between_operations=config.ridehailing_operator_config.operations_start,
    #    operation_duration=global_config.ridehailing_operator_config.operations_duration,
    #    available_modes=available_vehicle_modes_ridehailing,
    #    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ridehailing_operator_config.recharge_threshold,
    #    allow_queue=False,
    algo=time_minimizing_charging_allocation,
)


# Initialize operators
ridehailing_operator_0 = RideHailingOperator(
    env=env,
    fleet=ride_hailing_fleet_0,
    charging_infrastructure=charging_infrastructure_0,
    operations=ridehailing_operations_0,
    search_engine=search_engine["ride_hailing_0"],
    allocation_engine=vehicle_assignment_engine["ride_hailing_0"],
)

ridehailing_operator_1 = RideHailingOperator(
    env=env,
    fleet=ride_hailing_fleet_1,
    charging_infrastructure=charging_infrastructure_1,
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
    charging_infrastructure_0,
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
    demand_profile,
    di,
    world,
    config.demand_modifier_files,
    config.seed,
    mode="ride_hailing",
)
env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

env.run(until=config.end_time - 1e-8)
world.simulation_finished.succeed()
env.run(until=config.end_time)

logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Save Tracking Data                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

pd.DataFrame.from_records(vehicles_track).to_csv(
    f"data/output/tracking/{output_timestamp}_vehicles.csv", index=False
)

# stack charging infra tracks
c0 = pd.DataFrame.from_records(charging_stations_track_0)
c1 = pd.DataFrame.from_records(charging_stations_track_1)
c0["infra"] = 0
c1["infra"] = 1

pd.concat([c0, c1]).to_csv(
    f"data/output/tracking/{output_timestamp}_charging_stations.csv", index=False
)

avg_infra_util_0 = (
    pd.DataFrame.from_records(charging_stations_track_0)["_plugs.count"]
    / separate_charging_capacity_list[0]
).mean()

avg_infra_util_1 = (
    pd.DataFrame.from_records(charging_stations_track_1)["_plugs.count"]
    / separate_charging_capacity_list[0]
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

# Open the CSV file in append mode
with open("data/output/run_configs.csv", "a", newline="\n", encoding="utf-8") as file:
    # Create a CSV writer object
    writer = csv.writer(file)

    # Write a row to the CSV file
    writer.writerow(
        [
            output_timestamp,
            os.path.basename(__file__),
            config.end_time,
            time.time() - real_start_time,
            config.ridehailing_operator_config.n_autonomous_cars,
            config.get_charging_infrastructure_config().number_of_charging_stations,
            separate_charging_capacity_list[0],
            config.get_charging_infrastructure_config().charging_station_power_list[0],
            config.seed,
            service_rate_fleet_0,
            service_rate_fleet_1,
            avg_infra_util_0,
            avg_infra_util_1,
            f"{'random_SOC_init' if config.get_ridehailing_vehicle_config('autonomouscar').initial_SoC == 0 else ''}, queue_size: {config.get_charging_infrastructure_config().charging_station_queue_size_list[0]}, allocation_penalty: {config.ridehailing_operator_config.allocation_penalty}",
        ]
    )
