from __future__ import annotations

from typing import TYPE_CHECKING, Any
import torch
import math
import h3
from functools import cached_property
import numpy as np
from simulation.helper.enums import USER_STATE_TO_IDX, NUM_USER_STATES, UserState

if TYPE_CHECKING:
    from simulation.environment.geodesic_environment import GeodesicEnvironment
    from simulation.vehicle.vehicle import Vehicle
    from simulation.agent.user.user import User
    from simulation.infrastructure.charging_stations.charging_station import ChargingStation


class FeatureExtractor:

    def __init__(self, geo_env: GeodesicEnvironment, cs_locations: list[str]) -> None:
        self.geo_env = geo_env
        self.cs_coords_meters = self._transform_to_meters(np.array([h3.cell_to_latlng(cs_location) for cs_location in cs_locations], dtype=np.float32))
        self._fleet_encodings = None
        self.MAX_CS_CAPACITY = 10

        max_enum_val = max(state.value for state in UserState)
        self.LOOKUP_ARRAY = np.zeros(max_enum_val + 1, dtype=np.int64)

        for state, idx in USER_STATE_TO_IDX.items():
            self.LOOKUP_ARRAY[state.value] = idx
        pass

    @cached_property
    def meters_per_deg_lat(self):
        _, min_lat, _, max_lat = self.geo_env.getLayer("bounding_box").total_bounds
        
        ref_lat = (min_lat + max_lat) / 2.0
        
        return 111132.954 - 559.822 * math.cos(2 * math.radians(ref_lat))

    @cached_property
    def meters_per_deg_long(self):
        _, min_lat, _, max_lat = self.geo_env.getLayer("bounding_box").total_bounds
        
        ref_lat = (min_lat + max_lat) / 2.0
        return 111412.84 * math.cos(math.radians(ref_lat))

    @cached_property
    def max_distance(self) -> float:
        """Computes the maximum manhattan distance within the environment bounding box.
        """
        bbox_gdf = self.geo_env.getLayer("bounding_box")
        utm_bbox = bbox_gdf.to_crs(self.geo_env.utm_epsg)
        min_lat, min_long, max_lat, max_long = utm_bbox.total_bounds
        max_dist = (max_lat - min_lat) + (max_long - min_long)

        return max_dist
    
    @cached_property
    def max_span(self) -> float:
        """Computes the maximum single dimension (longest side) within the city bounding box in meters.
        
        This replaces the old Manhattan distance summation to prevent spatial distortion 
        during neural network coordinate normalization.
        """
        min_lng, min_lat, max_lng, max_lat = self.geo_env.getLayer("bounding_box").total_bounds
        
        width_meters = (max_lng - min_lng) * self.meters_per_deg_long
        height_meters = (max_lat - min_lat) * self.meters_per_deg_lat
        
        return float(max(width_meters, height_meters))

    def _transform_to_meters(self, coords: np.ndarray) -> np.ndarray:
        """
        Converts raw GPS coordinates [Lat, Lng] to flat linear meters 
        relative to the environment's bounding box origin.
        
        Args:
            coords: np array of shape (..., 2) containing [latitude, longitude]        
        Returns:
            np array of the same shape containing [X_meters, Y_meters]
        """
        min_lng, min_lat, _, _ = self.geo_env.getLayer("bounding_box").total_bounds
        
        lats = coords[..., 0]
        lngs = coords[..., 1]
        
        shifted_lng = lngs - min_lng
        shifted_lat = lats - min_lat
        
        x_meters = shifted_lng * self.meters_per_deg_long
        y_meters = shifted_lat * self.meters_per_deg_lat
        
        return np.stack([x_meters, y_meters], axis=-1).astype(np.float32)

    def _normalize_coordinates(self, coords_meters: np.ndarray) -> np.ndarray:
        """Uniformly normalizes UTM meter coordinates to a strict [-1, 1] range.
        Preserves true city aspect ratio so the neural network scales space perfectly.
        """
        return (coords_meters / self.max_span) * 2.0 - 1.0

    def normalize_distances(self, distances_array):
        """
        Normalizes a np array of distance arrays to a [0, 1] range.
        In-place operation for maximum speed and memory efficiency.
        """
        distances_array = np.asarray(distances_array, dtype=np.float32)
        distances_array /= self.max_distance
        
        np.clip(distances_array, 0.0, 1.0, out=distances_array)
        
        return distances_array

    def _calc_batch_manhattan_distances(
        self, 
        coords_list1: list[np.ndarray], 
        coords_list2: list[np.ndarray]
    ) -> np.ndarray:
        """
        Efficiently calculates the pairwise Manhattan distance between two lists of meter coordinates.
        
        Args:
            coords_list1: List of np arrays containing [X_meters, Y_meters] (Length: M)
            coords_list2: List of np arrays containing [X_meters, Y_meters] (Length: N)
            
        Returns:
            A 2D np array of shape (M, N) containing normalized distances in the range [0.0, 1.0].
        """
        m1 = np.array(coords_list1, dtype=np.float32)
        m2 = np.array(coords_list2, dtype=np.float32)
        
        diff = m1[:, None, :] - m2
        
        raw_distances = np.sum(np.abs(diff), axis=-1)
        
        return raw_distances

    def _get_time_features(self, current_minute: int) -> tuple[float, float]:
        # 2 * pi / 1440 simplifies to pi / 720
        if current_minute is None:
            return -1, -1
        radians = current_minute * (math.pi / 720.0)
        
        sin_time = math.sin(radians)
        cos_time = math.cos(radians)
        
        return sin_time, cos_time

    def _encode_request(self, request=None) -> np.ndarray:
        if request is None:
            return np.array([0, -1, -1, -1, -1, -1, -1], dtype=np.float32)

        sin_time, cos_time = self._get_time_features(request.creation_time)

        norm_orig = self._normalize_coordinates(self._transform_to_meters(np.asarray(request.origin.getExactLocation())))
        norm_dest = self._normalize_coordinates(self._transform_to_meters(np.asarray(request.destination.getExactLocation())))
        return np.array([1, sin_time, cos_time, norm_orig[0], norm_orig[1], norm_dest[0], norm_dest[0]], dtype=np.float32)

    def _encode_reservation(self, reservation=None) -> np.ndarray:
        if reservation is None or reservation.is_operator:
            return np.array([0, -1, -1], dtype=np.float32)

        norm_coord = self._normalize_coordinates(self._transform_to_meters(np.asarray(reservation.requester.position.getExactLocation())))
        return np.array([1, norm_coord[0], norm_coord[1]], dtype=np.float32)

    def _encode_user_states(self, user_states: np.ndarray) -> np.ndarray:
        dense_indices = self.LOOKUP_ARRAY[user_states]
        
        one_hot = np.zeros((len(user_states), NUM_USER_STATES), dtype=np.float32)
        one_hot[np.arange(len(user_states)), dense_indices] = 1.0
        
        return one_hot

    def extract_user_features(self, users: list[User], time) -> np.ndarray:
        if len(users) == 0:
            return np.array([])

        states = self._encode_user_states(np.array([USER_STATE_TO_IDX[user.state] for user in users]))
        positions = self._normalize_coordinates(self._transform_to_meters(np.array([user.position.getExactLocation() for user in users], dtype=np.float32)))
        requests = np.array([self._encode_request(user.transport_request) for user in users], dtype=np.float32)
        sin_time, cos_time = self._get_time_features(time)
        time_array = np.full((len(users), 2), [sin_time, cos_time], dtype=np.float32)
        search_starts = np.array([self._get_time_features(user.search_start_time) for user in users], dtype=np.float32)
        search_ends = np.array([self._get_time_features(user.search_end_time) for user in users], dtype=np.float32)
        trip_starts = np.array([self._get_time_features(user.trip_start_time) for user in users], dtype=np.float32)
        
        return np.concatenate((states, positions, requests, time_array, search_starts, search_ends, trip_starts), axis=1)

    def extract_vehicle_features(self, fleets: list[list[Vehicles]], users, time) -> np.ndarray:
        fleets_array = np.array(fleets)

        if self._fleet_encodings is None:
            num_fleets, vehicles_per_fleet = fleets_array.shape
            identity = np.eye(num_fleets, dtype=np.float32)
            self._fleet_encodings = np.repeat(identity, vehicles_per_fleet, axis=0)

        vehicles = np.array([vehicle for fleet in fleets for vehicle in fleet], dtype=object)
        coords_meters = self._transform_to_meters(np.array([vehicle.position.getExactLocation() for vehicle in vehicles], dtype=np.float32))

        if len(users) == 0:
            user_distances_normalized = np.array([], dtype=np.float32)

        else:
            user_coords_meters = self._transform_to_meters(np.array([user.position.getExactLocation() for user in users], dtype=np.float32))
            user_distances_normalized = (self.normalize_distances(self._calc_batch_manhattan_distances(coords_meters, user_coords_meters)))


        coords_normalized = self._normalize_coordinates(coords_meters)
        in_use = np.array([int(vehicle.state.parent is not None and vehicle.state.parent.name == 'TRANSPORTING') for vehicle in vehicles], dtype=np.float32)
        requests = np.array([self._encode_request(vehicle.current_request) for vehicle in vehicles], dtype=np.float32)
        reservations = np.array([self._encode_reservation(vehicle.current_reservation) for vehicle in vehicles], dtype=np.float32)
        cs_distances_normalized = (self.normalize_distances(self._calc_batch_manhattan_distances(coords_meters, self.cs_coords_meters)))

        SoCs = np.array([vehicle.energy_system.current_energy_relative for vehicle in vehicles], dtype=np.float32)
        sin_time, cos_time = self._get_time_features(time)
        time_array = np.full((vehicles.size, 2), [sin_time, cos_time], dtype=np.float32)
        return np.concatenate((self._fleet_encodings, in_use[:, np.newaxis], reservations, requests, SoCs[:, np.newaxis], coords_normalized, time_array), axis=1), cs_distances_normalized, user_distances_normalized

    def extract_charging_stations_features(self, charging_stations: list[ChargingStation], vehicles: Any) -> dict[str, torch.Tensor]:
        coords_normalized = self._normalize_coordinates(self.cs_coords_meters)
        power = np.array([charging_station.power / 100 for charging_station in charging_stations], dtype=np.float32)
        # TODO: exted if necessary (capacity etc) for now simplified to 1
        return np.concatenate((coords_normalized, power[:, np.newaxis]) , axis=1)