from pathlib import Path

import pandas as pd;

from simulation.world.demand.demand_factory import DemandFactory

pd.set_option('display.max_columns', None)
import simpy
import simulation.agent.user as user
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.operator.shared_vehicle_allocation_engine import SharedVehicleAllocationEngine
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.tasks.transport_task import TransportTask

import geopandas as gpd

# Simulation Environment
from simulation.world.demand.demand_importer import DemandImporter, SpatialResolution

env = simpy.Environment()

# Configure Logging
import logging

# Make it beautiful
logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)
logger = logging.getLogger()

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)

# Add Custom Filters
cf = SimulationContextFilter(filter_name='add_env', extra=env)
edf = ExtraDefaultFilter(filter_name = "add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)

p = Path('/Users/demircanm/sciebo/IS3/Research_Projects/HeterogeneousFleetManagement/01_Fleet_Sizing/0_Data/Berlin/shared_vehicle_trips_berlin.csv')
di = DemandImporter(spatial_resolution = SpatialResolution.HEX_7)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

demand_factory = DemandFactory(env, demand_profile, di)

env.process(demand_factory.generate_demand())

print("Debug")


def load_environment():
  "Move this into a seperate file"
  # Read Environment Files
  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_bounding_box.geojson"

  with open(filename) as file:
    env_df = gpd.read_file(file)

  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_hex_9.geojson"
  with open(filename) as file:
    env_df_hex_9 = gpd.read_file(file, driver= "GeoJSON")

  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_hex_8.geojson"
  with open(filename) as file:
    env_df_hex_8 = gpd.read_file(file)

  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_hex_7.geojson"
  with open(filename) as file:
    env_df_hex_7 = gpd.read_file(file)


  geodesic_environment = GeodesicEnvironment()
  geodesic_environment.addLayer("bounding_box", env_df)
  geodesic_environment.addLayer("hex_9", env_df_hex_9)
  geodesic_environment.addLayer("hex_8", env_df_hex_8)
  geodesic_environment.addLayer("hex_7", env_df_hex_7)

  return geodesic_environment

# Load Spatial Environment
load_environment()

# Dummy Tasks
pos = GeodesicPosition(52.52823, 13.35555) # (Lat, Lng)

hex_id, hexagon = pos.get_hexagon(8)
hex_id, hexagon = pos.get_hexagon(8)


task = TransportTask(pos, pos)
search_engine = SharedVehicleSearchEngine(env)
vehicle_assignment_engine = SharedVehicleAllocationEngine(env)


# x = user.User(pos, task, search_engine, search_engine, vehicle_assignment_engine, env)

# env.process(x.run())

# def run_agents():
#     while True:
#         x = user.User(pos, task, search_engine, search_engine, vehicle_assignment_engine, env)
#         y = user.User(pos, task, search_engine, search_engine,  vehicle_assignment_engine, env)
#         env.process(x.run())
#         env.process(y.run())
#         yield env.timeout(100)
# env.process(run_agents())

env.run(until = 60*24)

print(DemandFactory.counter)
#vehicle = SharedVehicle(pos)
#print(x.position)
#vehicle.mount(x)
#print(vehicle)
#vehicle.dismount(x)
#print(vehicle)
#vehicle.dismount(x)


# import simpy
# import random
# import statistics
#
# wait_times = []
#
#
# class Theater(object):
#     def __init__(self, env, num_cashiers, num_ushers, num_servers):
#         self.env = env
#         self.cashier = simpy.Resource(env, num_cashiers)
#         self.usher = simpy.Resource(env, num_ushers)
#         self.server = simpy.Resource(env, num_servers)
#
#
#     def purchase_ticket(self, moviegoer):
#         yield self.env.timeout(random.randint(60, 180))
#
#     def check_ticket(self, moviegoer):
#         yield self.env.timeout(random.randint(1, 5))
#
#     def sell_food(self, moviegoer):
#         yield self.env.timeout(random.randint(60, 300))
#
# def go_to_movies(env, moviegoer, theater):
#     # Moviegoer arrives at the theater
#     arrival_time = env.now
#
#     with theater.cashier.request() as request:
#         yield request
#         yield env.process(theater.purchase_ticket(moviegoer))
#
#     with theater.usher.request() as request:
#         yield request
#         yield env.process(theater.check_ticket(moviegoer))
#
#     if random.choice([True, False]):
#             with theater.server.request() as request:
#                 yield request
#                 yield env.process(theater.sell_food(moviegoer))
#
#     # Moviegoer heads into the theater
#     wait_times.append(env.now - arrival_time)
#
# def run_theater(env, num_cashiers, num_servers, num_ushers):
#     theater = Theater(env, num_cashiers, num_servers, num_ushers)
#
#     for moviegoer in range(3):
#         env.process(go_to_movies(env, moviegoer, theater))
#
#     while True:
#         yield env.timeout(12)  # Wait a bit before generating a new person
#
#         moviegoer += 1
#         env.process(go_to_movies(env, moviegoer, theater))
#
# def get_average_wait_time(wait_times):
#     return statistics.mean(wait_times)
#
# def main():
#   # Setup
#   random.seed(42)
#   num_cashiers, num_servers, num_ushers = [1, 1, 1]
#
#   # Run the simulation
#   env = simpy.Environment()
#   env.process(run_theater(env, num_cashiers, num_servers, num_ushers))
#   env.run(until=90*60)
#
#   # View the results
#   average_wait = get_average_wait_time(wait_times)
#   print(
#       "Running simulation...",
#       f"\nThe average wait time is {average_wait/60} minutes.",
#   )
#
#
