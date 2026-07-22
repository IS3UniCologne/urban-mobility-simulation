import numpy as np
import math
import h3
from simulation.vehicle.vehicle import Vehicle


def calc_cs_distances(cs_locations: list[str], vehicle_coordinates: list[tuple[float, float]]) -> np.ndarray:
    cs_coords = np.array([h3.cell_to_latlng(loc) for loc in cs_locations], dtype=np.float32)
    veh_coords = np.array(vehicle_coordinates, dtype=np.float32)

    ref_lat = np.mean(cs_coords[:, 0])
    
    METERS_PER_DEG_LAT = 111132.0
    METERS_PER_DEG_LON = np.cos(np.radians(ref_lat)) * 111320.0

    diff = veh_coords[:, None, :] - cs_coords
    
    dx = diff[..., 1] * METERS_PER_DEG_LON
    dy = diff[..., 0] * METERS_PER_DEG_LAT

    return np.abs(dx) + np.abs(dy)


def get_time_features(current_minute: int) -> tuple[float, float]:
    # 2 * pi / 1440 simplifies to pi / 720
    radians = current_minute * (math.pi / 720.0)
    
    sin_time = math.sin(radians)
    cos_time = math.cos(radians)
    
    return sin_time, cos_time

def encode_user_states(users: list) -> np.ndarray:
    """
    Takes a list of user objects and returns a one-hot encoded matrix 
    of shape (num_users, num_states).
    """
    state_indices = [STATE_TO_IDX[user.state] for user in users]
    
    one_hot_matrix = np.eye(NUM_STATES, dtype=np.float32)[state_indices]
    
    return one_hot_matrix

#def construct_vehicle_tokens(fleets: list[list[Vehicle]])