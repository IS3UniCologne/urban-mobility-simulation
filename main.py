from pathlib import Path

import pandas as pd;

from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.world import World

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
  geodesic_environment.get_centroid("871f1d7b3ffffff")
  return geodesic_environment

# Load Spatial Environment
load_environment()

# Vehicles
# TODO

car_1 = SharedCar(env, GeodesicPosition(52.59, 13.35))
car_2 = SharedCar(env, GeodesicPosition(55.59, 13.35))

kick_scooter = SharedKickScooter(env, GeodesicPosition(52.59, 13.35))

fleet = MixedSharedVehicleFleet()
fleet.add_shared_vehicle(car_1)
fleet.add_shared_vehicle(car_2)
fleet.add_shared_vehicle(kick_scooter)

pos = GeodesicPosition(52.59, 13.35)
hex_id, geometry = pos.get_hexagon()
x,y,z,t = fleet.get_vehicles_in_area(hex_id)

env.run(until = 360)

print(DemandFactory.counter)
