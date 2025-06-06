##Imports
# Standard library imports
import csv
import logging
import os
import time
from datetime import datetime

import pandas as pd

# Third-party library imports
import simpy

# Imports world related modules
from simulation.agent.user import User
from simulation.environment.geodesic_environment import GeodesicEnvironment

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
from simulation.operator.operations_management.ridehailing_uncoordinated_charging_operations import (
    RideHailingUncoordinatedChargingOperations,
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

# Change working directory to path of this file
# working_dir = Path(__file__).parent
# os.chdir(working_dir)


# Initialize Configuration Object
config = Configuration()


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Logging                                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Log Level
log_level = config.settings.LOG_LEVEL
file_log_level = config.settings.FILE_LOG_LEVEL

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)
logging.getLogger("docplex.util.environment.logger").setLevel(logging.WARNING)

logger = logging.getLogger()

output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
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


if (
    config.mode_choice_model.MODE_CHOICE_STRATEGY
    == ModeChoiceStrategy.SUBSTITUTION_AWARE
):
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

# TODO: n_ridehailing cars needs to be set to 0 in the toml file

# Bidding Streategy Parameters
bid_default = config.ride_hailing_global.BID_DEFAULT
bid_decay = config.ride_hailing_global.BID_DECAY
bidding_parameters = {"bid_default": bid_default, "bid_decay": bid_decay}

###### End RideHailing Fleet Configuration ######


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
population_factory = PopulationFactory(
    config.population.RIDE_HAILING_POPULATION_PROBABILITIES
)

# Load Spatial Environment and the environment files
load_geodesic_environment()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Charging Infrastructure                 #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


# for this scenario, we assume same locations, but split up capacity
separate_charging_capacity_list = [
    c / 2 for c in config.charging_infrastructure.CHARGING_STATION_CAPACITY
]

charging_infrastructure_0 = ChargingInfrastructure(
    env,
    config.charging_infrastructure.LOCATIONS,
    config.charging_infrastructure.CHARGING_STATION_POWER,
    separate_charging_capacity_list,
    config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE,
    reset=True,
)

charging_infrastructure_1 = ChargingInfrastructure(
    env,
    config.charging_infrastructure.LOCATIONS,
    config.charging_infrastructure.CHARGING_STATION_POWER,
    separate_charging_capacity_list,
    config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE,
    reset=True,
)

# track charging stations
charging_stations_track_0 = []
charging_stations_track_1 = []


def track_charging_stations(infra, target):  # noqa: ANN001, ANN201
    while True:
        yield env.timeout(1)
        values = [
            {
                "time": env._now,  # noqa: SLF001
                "_location": d["_location"],
                "_plugs.count": d["_plugs"].count,
                "_plugs.queuesize": len(d["_plugs"].queue),
            }
            for d in [
                tracking.dump(tracking._get_uid(x))[1]  # noqa: SLF001
                for x in infra.charging_stations
            ]
        ]
        target.extend(values)


env.process(
    track_charging_stations(charging_infrastructure_0, charging_stations_track_0)
)
env.process(
    track_charging_stations(charging_infrastructure_1, charging_stations_track_1)
)


#### End Charging Infrastructure Configuration #####

# # # # # # # # # # # # # # # # # # # # # #

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
    "./data/infrastructure",
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

available_vehicle_modes_ridehailing = ["AutonomousCar"]
available_vehicle_modes_supply_ride_hailing = [
    config.ride_hailing_global.N_AUTONOMOUS_CARS
]

# Get the supply probability from supply file
supply_prob = pd.read_csv(config.path.PATH_VEHICLE_SUPPLY)

ride_hailing_fleet_0 = generate_AV_fleet(
    env=env, distribution=supply_prob, n=config.ride_hailing_global.N_AUTONOMOUS_CARS
)

ride_hailing_fleet_1 = generate_AV_fleet(
    env=env, distribution=supply_prob, n=config.ride_hailing_global.N_AUTONOMOUS_CARS
)


# track vehicles in fleets
vehicles_track = []


def track_fleets(fleet_id):  # noqa: ANN001, ANN201
    # attention: this only works because we do not dynamically create and destroy vehicles like we do with users!
    tracked_list = tracking.list_tracked("RideHailingAV")

    while True:
        yield env.timeout(1)
        envtime, values = (
            env._now,  # noqa: SLF001
            {
                "_fleet": fleet_id,
                "_state": [
                    tracking.get(x, "state")[1]
                    for x in tracked_list
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
                "_current_state_of_charge": [
                    tracking.get(x, "_current_state_of_charge")[1]
                    for x in tracked_list
                    if tracking.get(x, "_fleet")[1].id == fleet_id
                ],
                "_vdt": [
                    tracking.get(x, "_distance_travelled")[1]
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

# if queue sizes at charging stations are all zero, we should account for that in the operations
# there can be more clever and nuanced approaches, but as a rule of thumb, we should not allow operations to send vehicles to charging stations that are full if we don't allow queueing
allow_queue = sum(config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE) > 0

# Initialize fleet operations
ridehailing_operations_0 = RideHailingUncoordinatedChargingOperations(
    env=env,
    distance_matrix=distance_matrix,
    time_between_operations=config.ride_hailing_operators[0].OPERATIONS_START,
    operation_duration=config.ride_hailing_operators[0].OPERATIONS_DURATION,
    available_modes=available_vehicle_modes_ridehailing,
    available_modes_supply=available_vehicle_modes_supply_ride_hailing,
    state_of_charge_threshold=config.ride_hailing_operators[0].RECHARGE_THRESHOLD,
    allow_queue=allow_queue,
)

ridehailing_operations_1 = RideHailingUncoordinatedChargingOperations(
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
    env, world, config.path.PATH_DEMAND_MODIFIERS, mode="ride_hailing"
)
env.process(demand_factory.generate_demand())

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Run Simulation.                         #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

env.run(until=config.experiment_management.END_TIME - 1e-8)
world.simulation_finished.succeed()
env.run(until=config.experiment_management.END_TIME)

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

fleet_0_transactions = ridehailing_operator_0.transaction_df
fleet_1_transactions = ridehailing_operator_1.transaction_df

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
            config.experiment_management.END_TIME,
            time.time() - real_start_time,
            config.ride_hailing_global.N_AUTONOMOUS_CARS,
            config.charging_infrastructure.NUMBER_OF_CHARGING_STATIONS,
            separate_charging_capacity_list[0],
            config.charging_infrastructure.CHARGING_STATION_POWER[0],
            config.random_manager.SEED,
            service_rate_fleet_0,
            service_rate_fleet_1,
            avg_infra_util_0,
            avg_infra_util_1,
            f"{'random_SOC_init' if config.ride_hailing_vehicles.get('AutonomousCar').INITIAL_SOC == 0 else ''}, queue_size:{config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE[0]}",
        ]
    )
