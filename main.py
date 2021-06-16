from pathlib import Path

# Random Number Seed
import random
import numpy
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
numpy.random.seed(RANDOM_SEED)

import pandas as pd

from simulation.operator.fleet_factory import generate_fleet_config, generate_mixed_fleet
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.world import World

pd.set_option('display.max_columns', None)
import simpy
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter
from simulation.operator.shared_vehicle_allocation_engine import SharedVehicleAllocationEngine
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
import geopandas as gpd

# Simulation Environment
from simulation.world.demand.demand_importer import DemandImporter, SpatialResolution

env = simpy.Environment()

# Configure Logging
import logging

# Make it beautiful
logging.basicConfig(format='%(asctime)s [%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logger = logging.getLogger()

# Block Logger of third party software
logging.getLogger("fiona").setLevel(logging.WARNING)

# Add Custom Filters
cf = SimulationContextFilter(filter_name='add_env', extra=env)
edf = ExtraDefaultFilter(filter_name = "add_default_value")
logger.addFilter(cf)
logger.addFilter(edf)


# Operator Modules
search_engine = SharedVehicleSearchEngine(env)
payment_engine = search_engine
vehicle_assignment_engine = SharedVehicleAllocationEngine(env)

# World
world = World(env, search_engine, search_engine, vehicle_assignment_engine)

# Demand
p = Path('/Users/demircanm/sciebo/IS3/Research_Projects/HeterogeneousFleetManagement/01_Fleet_Sizing/0_Data/Berlin/shared_vehicle_trips_berlin.csv')
di = DemandImporter(spatial_resolution = SpatialResolution.HEX_7)

demand_profile = di.extract_spatio_temporal_demand_estimates(p)

demand_factory = DemandFactory(env, demand_profile, di, world)

env.process(demand_factory.generate_demand())

# Environment (Spatial)
def load_environment():
  "Move this into a seperate file"
  # Read Environment Files
  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_bounding_box.geojson"

  with open(filename) as file:
    env_df = gpd.read_file(file)

  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_hex_9.geojson"
  with open(filename) as file:
    env_df_hex_9 = gpd.read_file(file, driver= "GeoJSON")
    env_df_hex_9.set_index('hex_id_9', inplace=True)

  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_hex_8.geojson"
  with open(filename) as file:
    env_df_hex_8 = gpd.read_file(file)
    env_df_hex_8.set_index('hex_id_8', inplace=True)

  filename = "/Users/demircanm/Development/urban-mobility-simulation/data/environment/geodesic/env_hex_7.geojson"
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

# Vehicles
supply_prob = pd.read_csv('data/supply/vehicle_supply_distribution_hex_7.csv')

fleet_config = generate_fleet_config(supply_prob, n_cars = 1000, n_scooter = 0, n_kick_scooter=0, n_bikes=0)
mixed_fleet = generate_mixed_fleet(env, fleet_config)

# Artifically add vehicle (see world add new user)
# Access to underlying geodesic environment
# geo_env = GeodesicEnvironment.getInstance()
# from simulation.environment.geodesic_position import GeodesicPosition
# from simulation.vehicle.shared_car import SharedCar
#
# rdm_lat, rdm_lng = geo_env.get_random_position('871f1d498ffffff')
# pos = GeodesicPosition(rdm_lat, rdm_lng)
# car = SharedCar(env, pos)
# car_2 = SharedCar(env, pos)
# mixed_fleet.add_shared_vehicle(car)
# mixed_fleet.add_shared_vehicle(car_2)

# Register Modules
search_engine.register_fleet(mixed_fleet)

env.run(until = 720)

print(DemandFactory.counter)

