"""Geodesic helper module for spatial indexing and coordinate transformations.

This module provides utilities for fast spatial vehicle indexing using R-tree
and coordinate transformations between WGS84 and UTM coordinate systems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyproj import Transformer
from rtree.index import Index

from simulation.environment.geodesic_position import GeodesicPosition

if TYPE_CHECKING:
    from simulation.environment.position import Position
    from simulation.helper.configuration.enums import VehicleType
    from simulation.vehicle.vehicle import Vehicle


class FastSpatialVehicleIndex:
    """
    A fast spatial index for efficient vehicle radius lookups.

    This class uses an R-tree index for fast spatial searches based on
    Euclidean distance in meters (using UTM coordinates).
    """

    def __init__(self, utm_epsg: str) -> None:
        """
        Set up a fast (approximate) spatial index for radius lookups based on euclidean distance (in meters).

        Parameters
        ----------
        utm_epsg : str
            The UTM zone of the simulated city in EPSG reference. For Berlin e.g. it's "epsg:25832".
        """
        self._transformer = Transformer.from_crs(
            crs_from="epsg:4326", crs_to=utm_epsg, always_xy=True
        )
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
        x, y = self._transformer.transform(
            *vehicle.position.getExactLocation(geojson=True)
        )
        v_type = vehicle.vehicle_type
        self._coords[vehicle.id] = (x, y, v_type)

        if v_type not in self._rtrees:
            self._rtrees[v_type] = Index()
        self._rtrees[v_type].insert(vehicle.id, (x, y, x, y))

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
        x, y, v_type = coords_info
        cx, cy = self._transformer.transform(
            *vehicle.position.getExactLocation(geojson=True)
        )
        if cx != x or cy != y:
            raise RuntimeError(
                f"Vehicle {vehicle.id} position changed since insertion; "
                "index is inconsistent."
            )
        self._rtrees[v_type].delete(vehicle.id, (x, y, x, y))

    def radius_search(
        self,
        point: GeodesicPosition,
        radius: float | int | dict[VehicleType, float | int],
    ) -> set[int]:
        """
        Search for vehicle IDs within a certain radius of a point.

        Attention: This is using a square box, not a circle, it is an overestimation of a radius search!

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
        qx, qy = self._transformer.transform(*point.getExactLocation(geojson=True))
        vehicles_in_bbox: set[int] = set()

        if isinstance(radius, dict):
            for v_type, r in radius.items():
                if v_type in self._rtrees:
                    bounds = (qx - r, qy - r, qx + r, qy + r)
                    vehicles_in_bbox.update(self._rtrees[v_type].intersection(bounds))
        else:
            bounds = (qx - radius, qy - radius, qx + radius, qy + radius)
            for rtree in self._rtrees.values():
                vehicles_in_bbox.update(rtree.intersection(bounds))

        return vehicles_in_bbox

    def transform_point(self, point: GeodesicPosition) -> tuple[float, float]:
        """
        Transform a geodesic position to UTM coordinates.

        Parameters
        ----------
        point : GeodesicPosition
            The position to transform.

        Returns
        -------
        tuple[float, float]
            The UTM coordinates (x, y).
        """
        return self._transformer.transform(*point.getExactLocation(geojson=True))


class FastSpatialDestinationIndex:
    """
    A fast spatial index for efficient vehicle destination radius lookups.

    Tracks en-route vehicles based on their destination and ETA.
    """

    def __init__(self, utm_epsg: str) -> None:
        """
        Set up a fast (approximate) spatial index for destination radius lookups.

        Parameters
        ----------
        utm_epsg : str
            The UTM zone of the simulated city in EPSG reference.
        """
        self._transformer = Transformer.from_crs(
            crs_from="epsg:4326", crs_to=utm_epsg, always_xy=True
        )
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

        if vehicle.id in self._coords:
            self.delete(vehicle)

        x, y = self.transform_point(vehicle.destination)
        self._coords[vehicle.id] = (x, y)
        self._etas[vehicle.id] = getattr(vehicle, "estimated_completion_time", 0.0)

        self._rtree.insert(vehicle.id, (x, y, x, y))

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
        x, y = coords_info

        self._rtree.delete(vehicle.id, (x, y, x, y))

    def radius_search(
        self, point: GeodesicPosition, radius: float | int, max_eta: float | None = None
    ) -> set[int]:
        """
        Search for vehicle IDs within a certain destination radius and ETA.

        TODO: Consider partitioned index or dynamic radius mapping if heterogeneous
        query needs arise (e.g., different radii per vehicle type). (similar to FastSpatialVehicleIndex)

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
        qx, qy = self.transform_point(point)
        vehicles_in_bbox: set[int] = set()

        bounds = (qx - radius, qy - radius, qx + radius, qy + radius)
        vehicles_in_bbox.update(self._rtree.intersection(bounds))

        if max_eta is not None:
            vehicles_in_bbox = {
                vid
                for vid in vehicles_in_bbox
                if self._etas.get(vid, float("inf")) <= max_eta
            }

        return vehicles_in_bbox

    def transform_point(
        self, point: GeodesicPosition | Position
    ) -> tuple[float, float]:
        """
        Transform a geodesic position to UTM coordinates.

        Parameters
        ----------
        point : GeodesicPosition | Position
            The position to transform.

        Returns
        -------
        tuple[float, float]
            The UTM coordinates (x, y).
        """
        if not isinstance(point, GeodesicPosition):
            raise TypeError("Point must be a GeodesicPosition to get geojson location.")
        return self._transformer.transform(*point.getExactLocation(geojson=True))
