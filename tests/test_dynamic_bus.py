# tests/test_dynamic_bus.py
import pytest
import h3
import numpy as np
from simpy import Environment
from shapely.geometry import Polygon
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.world.world import World
from simulation.environment.geodesic_environment import GeodesicEnvironment
from tracking.tracking import Tracking
from learning.dynamic_bus_checkpoints import DynamicBusCheckpointProblem

@pytest.fixture
def problem():
    env = Environment()
    
    # Reset singletons if needed
    Configuration._instance = None
    World._instance = None
    Tracking._instance = None
    GeodesicEnvironment._instance = None
    
    # Create problem instance
    problem = DynamicBusCheckpointProblem(env)
    
    # Mock bus and related classes
    class MockBus:
        def __init__(self):
            self.position = GeodesicPosition(48.137154, 11.576124)  # Munich
            self.route = MockRoute()
            self._velocity = 10  # m/s
            self._dist_traveled = 0
            self._pickups = 0
            self._dropoffs = 0
            self._spawned = env.now
            self._state = "EN_ROUTE"
            self._id = "bus1"
            self._time = MockTime()
            self._has_reached_terminal = env.event()
        
        def _update_positions(self, new_position):
            self.position = new_position
    
    class MockRoute:
        def __init__(self):
            self.origin = GeodesicPosition(48.137154, 11.576124)
            self.destination = GeodesicPosition(48.147154, 11.586124)
            self.stops = [self.origin, self.destination]
        
        def route_stop_by_id(self, stop_id):
            return self.stops[stop_id]
    
    class MockTime:
        def now_as_str(self):
            return "2025-06-11 17:48:00"
    
    problem.bus = MockBus()
    problem._problem_config.checkpoints = [0]
    problem._problem_config.corridor = h3.grid_disk(
        h3.latlng_to_cell(48.137154, 11.576124, problem._action_res), k=2
    )
    problem.problem_init()
    return problem

def test_latlng_to_cell(problem):
    lat, lng = problem.bus.position.getExactLocation()
    hex_id = h3.latlng_to_cell(lat, lng, problem._action_res)
    assert isinstance(hex_id, str), "Hex ID should be a string"
    assert h3.is_valid_cell(hex_id), "Hex ID should be valid"

def test_move_in_layer(problem):
    hex_id = h3.latlng_to_cell(
        *problem.bus.position.getExactLocation(), resolution=problem._action_res
    )
    new_hex = problem._geodesic_env.move_in_layer(hex_id, "up")
    assert h3.is_valid_cell(new_hex), "New hex should be valid"
    assert new_hex in h3.grid_ring(hex_id, 1), "New hex should be a neighbor"

def test_cells_to_h3shape(problem):
    assert isinstance(problem._corridor_poly, Polygon), "Corridor should be a Polygon"
    assert problem._corridor_poly.is_valid, "Corridor polygon should be valid"

def test_grid_path_cells(problem):
    current_hex = problem.bus.position.get_hexagon_id(problem._action_res)
    dest_hex = problem.bus.route.destination.get_hexagon_id(problem._action_res)
    path = h3.grid_path_cells(current_hex, dest_hex)
    assert isinstance(path, list), "Path should be a list"
    assert all(h3.is_valid_cell(h) for h in path), "All path cells should be valid"
    assert path[0] == current_hex, "Path should start at current hex"
    assert path[-1] == dest_hex, "Path should end at destination"

def test_take_action(problem):
    initial_hex = problem.bus.position.get_hexagon_id(problem._action_res)
    problem._take_action("up")
    problem.env.run()
    new_hex = problem.bus.position.get_hexagon_id(problem._action_res)
    assert new_hex != initial_hex, "Bus should move to a new hex"
    assert new_hex in problem._corridor, "New hex should be in corridor"

# Add other test cases as needed: test_test_action_valid, test_demands_in_corridor, etc.