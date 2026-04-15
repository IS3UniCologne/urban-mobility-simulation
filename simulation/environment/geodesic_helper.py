"""Geodesic helper module for spatial indexing and coordinate transformations.

This module provides utilities for fast spatial vehicle indexing using R-tree
and coordinate transformations between WGS84 and UTM coordinate systems.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rtree.index import Index

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.enums import VehicleType
    from simulation.vehicle.vehicle import Vehicle

# Constant for meters per degree of latitude (approximately 111.32 km)
METERS_PER_DEGREE = 111320.0


class FastSpatialVehicleIndex:
    """
    A fast spatial index for efficient vehicle radius lookups.

    This class uses an R-tree index for fast spatial searches based on
    WGS84 coordinates and an equirectangular approximation for Euclidean distance in meters.
    """

    def __init__(self) -> None:
        """Set up a fast (approximate) spatial index for radius lookups based on WGS84 coordinates."""
        self._rtrees: dict[VehicleType, Index] = {}
        self._coords: dict[int, tuple[float, float, VehicleType]] = {}

    def insert(self, vehicle: Vehicle) -> None:
        """
        Insert a vehicle into the spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle to insert.
        """
        if vehicle.id in self._coords:
            raise RuntimeError(
                f"Vehicle {vehicle.id} already in spatial index; "
                "duplicate insert or ID collision across vehicle subclasses."
            )
        lng, lat = vehicle.position.getExactLocation(geojson=True)
        v_type = vehicle.vehicle_type
        self._coords[vehicle.id] = (lng, lat, v_type)

        if v_type not in self._rtrees:
            self._rtrees[v_type] = Index()
        self._rtrees[v_type].insert(vehicle.id, (lng, lat, lng, lat))

    def delete(self, vehicle: Vehicle) -> None:
        """
        Delete a vehicle from the spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle to delete.
        """
        coords_info = self._coords.pop(vehicle.id, None)
        if coords_info is None:
            raise RuntimeError(
                f"Vehicle {vehicle.id} not in spatial index; cannot delete."
            )
        lng, lat, v_type = coords_info
        clng, clat = vehicle.position.getExactLocation(geojson=True)
        if clng != lng or clat != lat:
            raise RuntimeError(
                f"Vehicle {vehicle.id} position changed since insertion; "
                "index is inconsistent."
            )
        self._rtrees[v_type].delete(vehicle.id, (lng, lat, lng, lat))

    def radius_search(
        self,
        point: GeodesicPosition,
        radius: float | int | dict[VehicleType, float | int],
    ) -> set[int]:
        """
        Search for vehicle IDs within a certain radius of a point.

        This uses a two-step approach:
        1. Bounding box search in WGS84 using the R-tree.
        2. Circular post-filtering using an equirectangular approximation for Euclidean distance in meters.

        Parameters
        ----------
        point : GeodesicPosition
            The center point of the search.
        radius : float | int | dict[VehicleType, float | int]
            The radius within which to search for vehicles (in meters).
            Can be a single radius for all vehicle types, or a dictionary
            mapping specific vehicle types to their respective search radii.

        Returns
        -------
        set[int]
            Return a set of vehicle IDs.
        """
        user_lng, user_lat = point.getExactLocation(geojson=True)
        lat_rad = math.radians(user_lat)
        cos_lat = math.cos(lat_rad)
        lng_meter_scale = METERS_PER_DEGREE * cos_lat

        vehicles_in_radius: set[int] = set()

        if isinstance(radius, dict):
            for v_type, r in radius.items():
                if v_type in self._rtrees:
                    delta_lat = r / METERS_PER_DEGREE
                    delta_lng = r / lng_meter_scale
                    bounds = (
                        user_lng - delta_lng,
                        user_lat - delta_lat,
                        user_lng + delta_lng,
                        user_lat + delta_lat,
                    )
                    candidates = self._rtrees[v_type].intersection(bounds)

                    radius_squared = r**2
                    for vid in candidates:
                        lng, lat, _ = self._coords[vid]
                        dx = (lng - user_lng) * lng_meter_scale
                        dy = (lat - user_lat) * METERS_PER_DEGREE
                        if (dx**2 + dy**2) <= radius_squared:
                            vehicles_in_radius.add(vid)
        else:
            delta_lat = radius / METERS_PER_DEGREE
            delta_lng = radius / lng_meter_scale
            bounds = (
                user_lng - delta_lng,
                user_lat - delta_lat,
                user_lng + delta_lng,
                user_lat + delta_lat,
            )
            radius_squared = radius**2

            for rtree in self._rtrees.values():
                candidates = rtree.intersection(bounds)
                for vid in candidates:
                    lng, lat, _ = self._coords[vid]
                    dx = (lng - user_lng) * lng_meter_scale
                    dy = (lat - user_lat) * METERS_PER_DEGREE
                    if (dx**2 + dy**2) <= radius_squared:
                        vehicles_in_radius.add(vid)

        return vehicles_in_radius


class FastSpatialDestinationIndex:
    """
    A fast spatial index for efficient vehicle destination radius lookups.

    Tracks en-route vehicles based on their destination and ETA using WGS84 coordinates.
    """

    def __init__(self) -> None:
        """Set up a fast (approximate) spatial index for destination radius lookups."""
        self._rtree: Index = Index()
        self._coords: dict[int, tuple[float, float]] = {}
        self._etas: dict[int, float] = {}

    def insert(self, vehicle: Vehicle) -> None:
        """
        Insert or update a vehicle into the en-route spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle to insert.
        """
        if not hasattr(vehicle, "destination") or vehicle.destination is None:
            return
        if vehicle.destination == vehicle.position:
            # a vehicle at its destination is not en-route; skip indexing
            # TODO: warn caller?
            return

        if vehicle.id in self._coords:
            self.delete(vehicle)

        lng, lat = vehicle.destination.getExactLocation(geojson=True)
        self._coords[vehicle.id] = (lng, lat)
        self._etas[vehicle.id] = getattr(vehicle, "estimated_completion_time", 0.0)

        self._rtree.insert(vehicle.id, (lng, lat, lng, lat))

    def delete(self, vehicle: Vehicle) -> None:
        """
        Delete a vehicle from the en-route spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle to delete.
        """
        coords_info = self._coords.pop(vehicle.id, None)
        if coords_info is None:
            return

        self._etas.pop(vehicle.id, None)
        lng, lat = coords_info

        self._rtree.delete(vehicle.id, (lng, lat, lng, lat))

    def radius_search(
        self, point: GeodesicPosition, radius: float | int, max_eta: float | None = None
    ) -> set[int]:
        """
        Search for vehicle IDs within a certain destination radius and ETA.

        This uses a two-step approach:
        1. Bounding box search in WGS84 using the R-tree.
        2. Circular post-filtering using an equirectangular approximation for Euclidean distance in meters.

        Parameters
        ----------
        point : GeodesicPosition
            The center point of the search.
        radius : float | int
            The radius within which to search for vehicles (in meters).
        max_eta : float | None
            The maximum acceptable estimated completion time.

        Returns
        -------
        set[int]
            Return a set of vehicle IDs.
        """
        user_lng, user_lat = point.getExactLocation(geojson=True)
        lat_rad = math.radians(user_lat)
        cos_lat = math.cos(lat_rad)
        lng_meter_scale = METERS_PER_DEGREE * cos_lat

        delta_lat = radius / METERS_PER_DEGREE
        delta_lng = radius / lng_meter_scale
        bounds = (
            user_lng - delta_lng,
            user_lat - delta_lat,
            user_lng + delta_lng,
            user_lat + delta_lat,
        )

        candidates = list(self._rtree.intersection(bounds))
        vehicles_in_radius: set[int] = set()
        radius_squared = radius**2

        for vid in candidates:
            # Check ETA first for early exit
            if max_eta is not None and self._etas.get(vid, float("inf")) > max_eta:
                continue

            lng, lat = self._coords[vid]
            dx = (lng - user_lng) * lng_meter_scale
            dy = (lat - user_lat) * METERS_PER_DEGREE
            if (dx**2 + dy**2) <= radius_squared:
                vehicles_in_radius.add(vid)

        return vehicles_in_radius
