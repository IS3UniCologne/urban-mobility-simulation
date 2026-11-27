"""Spatial indexes for radius lookups over vehicles.

The indexes hold WGS84 coordinates in NumPy arrays.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.enums import VehicleType
    from simulation.vehicle.vehicle import Vehicle

# Constant for meters per degree of latitude (approximately 111.32 km)
METERS_PER_DEGREE = 111320.0

_INITIAL_CAPACITY = 64
# A NumPy call has a fixed cost, so narrowing to the longitude band only pays for a larger set
_NARROW_ABOVE = 2048
# Wider than the rounding error of a longitude, so the band never drops a point within reach
_BAND_MARGIN_DEG = 1e-9


class _PointSet:
    """
    Points keyed by vehicle id, in arrays without gaps.

    Each point carries one value that its index filters on.

    Parameters
    ----------
    value_dtype : type
        NumPy type of the value each point carries.
    """

    __slots__ = ("_ids", "_lats", "_lngs", "_rows", "_size", "_values")

    def __init__(self, value_dtype: type) -> None:
        self._ids = np.empty(_INITIAL_CAPACITY, dtype=np.int64)
        self._lngs = np.empty(_INITIAL_CAPACITY, dtype=np.float64)
        self._lats = np.empty(_INITIAL_CAPACITY, dtype=np.float64)
        self._values = np.empty(_INITIAL_CAPACITY, dtype=value_dtype)
        self._rows: dict[int, int] = {}
        self._size = 0

    def __len__(self) -> int:
        """Return the number of points."""
        return self._size

    def __contains__(self, vehicle_id: int) -> bool:
        """Return whether the vehicle has a point."""
        return vehicle_id in self._rows

    def add(
        self, vehicle_id: int, lng_deg: float, lat_deg: float, value: float
    ) -> None:
        """Add the point of a vehicle that has none.

        Parameters
        ----------
        vehicle_id : int
            Vehicle the point belongs to.
        lng_deg : float
            Longitude.
        lat_deg : float
            Latitude.
        value : float or int
            Value the point carries.
        """
        row = self._size
        if row == len(self._ids):
            self._grow()
        self._ids[row] = vehicle_id
        self._lngs[row] = lng_deg
        self._lats[row] = lat_deg
        self._values[row] = value
        self._rows[vehicle_id] = row
        self._size = row + 1

    def remove(self, vehicle_id: int) -> tuple[float, float]:
        """Remove the point of a vehicle.

        Parameters
        ----------
        vehicle_id : int
            Vehicle the point belongs to.

        Returns
        -------
        tuple of float
            Coordinates of the removed point as (longitude, latitude).
        """
        row = self._rows.pop(vehicle_id)
        coordinates = (float(self._lngs[row]), float(self._lats[row]))
        last = self._size - 1
        if row != last:
            # The last point fills the gap, so a lookup never reads a removed point
            moved_id = int(self._ids[last])
            self._ids[row] = moved_id
            self._lngs[row] = self._lngs[last]
            self._lats[row] = self._lats[last]
            self._values[row] = self._values[last]
            self._rows[moved_id] = row
        self._size = last
        return coordinates

    def candidates(
        self, position: GeodesicPosition, reach_m: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Measure the squared distance from a position to each point that can be within reach.

        We check every point when the index is small.
        In a larger set the candidates are the points in the longitude band around the position.
        A candidate can be farther away than the reach.

        Parameters
        ----------
        position : GeodesicPosition
            Position to measure from.
        reach_m : float or int
            Largest distance a caller accepts (meters).

        Returns
        -------
        tuple of numpy.ndarray
            Vehicle id, value and squared distance (square meters) of each candidate.
        """
        lng, lat = position.getExactLocation(geojson=True)
        lng_meter_scale = METERS_PER_DEGREE * math.cos(math.radians(lat))
        size = self._size
        ids = self._ids[:size]
        lngs = self._lngs[:size]
        lats = self._lats[:size]
        values = self._values[:size]
        if size > _NARROW_ABOVE:
            reach_deg = reach_m / lng_meter_scale + _BAND_MARGIN_DEG
            in_band = np.flatnonzero(np.abs(lngs - lng) <= reach_deg)
            ids, lngs, lats, values = (
                ids[in_band],
                lngs[in_band],
                lats[in_band],
                values[in_band],
            )
        dx = (lngs - lng) * lng_meter_scale
        dy = (lats - lat) * METERS_PER_DEGREE
        return ids, values, dx * dx + dy * dy

    def _grow(self) -> None:
        self._ids = np.concatenate((self._ids, np.empty_like(self._ids)))
        self._lngs = np.concatenate((self._lngs, np.empty_like(self._lngs)))
        self._lats = np.concatenate((self._lats, np.empty_like(self._lats)))
        self._values = np.concatenate((self._values, np.empty_like(self._values)))


class FastSpatialVehicleIndex:
    """Spatial index for radius lookups over vehicles at their position."""

    __slots__ = ("_points", "_type_codes")

    def __init__(self) -> None:
        self._points = _PointSet(value_dtype=np.intp)
        self._type_codes: dict[VehicleType, int] = {}

    def insert(self, vehicle: Vehicle) -> None:
        """Insert a vehicle into the spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            Vehicle to insert.

        Raises
        ------
        RuntimeError
            If the vehicle is already in the index.
        """
        if vehicle.id in self._points:
            raise RuntimeError(
                f"Vehicle {vehicle.id} already in spatial index; "
                "duplicate insert or ID collision across vehicle subclasses."
            )
        lng, lat = vehicle.position.getExactLocation(geojson=True)
        type_code = self._type_codes.setdefault(
            vehicle.vehicle_type, len(self._type_codes)
        )
        self._points.add(vehicle.id, lng, lat, type_code)

    def delete(self, vehicle: Vehicle) -> None:
        """Delete a vehicle from the spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            Vehicle to delete.

        Raises
        ------
        RuntimeError
            If the vehicle is not in the index or moved since its insertion.
        """
        if vehicle.id not in self._points:
            raise RuntimeError(
                f"Vehicle {vehicle.id} not in spatial index; cannot delete."
            )
        inserted_at = self._points.remove(vehicle.id)
        if vehicle.position.getExactLocation(geojson=True) != inserted_at:
            raise RuntimeError(
                f"Vehicle {vehicle.id} position changed since insertion; "
                "index is inconsistent."
            )

    def radius_search(
        self,
        point: GeodesicPosition,
        radius: float | int | dict[VehicleType, float | int],
    ) -> set[int]:
        """Search for vehicle IDs within a certain radius of a point.

        Parameters
        ----------
        point : GeodesicPosition
            Center of the search.
        radius : float or int or dict of VehicleType to float or int
            Search radius (meters).
            As a dictionary, one radius per vehicle type, which leaves out every type it does not name.

        Returns
        -------
        set of int
            IDs of the vehicles within the radius.
        """
        points = self._points
        if len(points) == 0:
            return set()

        if isinstance(radius, dict):
            ids, type_codes, distances_m2 = points.candidates(
                point, max(radius.values(), default=0)
            )
            # No squared distance is below zero, so a type without a radius never matches
            limits = np.full(len(self._type_codes), -1.0)
            for vehicle_type, type_radius in radius.items():
                type_code = self._type_codes.get(vehicle_type)
                if type_code is not None:
                    limits[type_code] = type_radius**2
            limit = limits[type_codes]
        else:
            ids, _, distances_m2 = points.candidates(point, radius)
            limit = radius**2

        return set(ids[distances_m2 <= limit].tolist())


class FastSpatialDestinationIndex:
    """
    A fast spatial index for efficient vehicle destination radius lookups.

    Tracks en-route vehicles based on their destination and ETA using WGS84 coordinates.
    """

    __slots__ = ("_points",)

    def __init__(self) -> None:
        self._points = _PointSet(value_dtype=np.float64)

    def insert(self, vehicle: Vehicle) -> None:
        """Insert or update a vehicle into the en-route spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            Vehicle to insert.
        """
        if not hasattr(vehicle, "destination") or vehicle.destination is None:
            return
        if vehicle.destination == vehicle.position:
            # a vehicle at its destination is not en-route; skip indexing
            # TODO: warn caller?
            return

        self.delete(vehicle)
        lng, lat = vehicle.destination.getExactLocation(geojson=True)
        eta = getattr(vehicle, "estimated_completion_time", 0.0)
        self._points.add(vehicle.id, lng, lat, eta)

    def delete(self, vehicle: Vehicle) -> None:
        """Delete a vehicle from the en-route spatial index.

        Parameters
        ----------
        vehicle : Vehicle
            Vehicle to delete.
        """
        if vehicle.id in self._points:
            self._points.remove(vehicle.id)

    def radius_search(
        self, point: GeodesicPosition, radius: float | int, max_eta: float | None = None
    ) -> set[int]:
        """Search for vehicle IDs within a certain destination radius and ETA.

        Parameters
        ----------
        point : GeodesicPosition
            Center of the search.
        radius : float or int
            Search radius (meters).
        max_eta : float or None
            Latest accepted estimated completion time. None accepts every time.

        Returns
        -------
        set of int
            IDs of the vehicles within the radius and the ETA.
        """
        points = self._points
        if len(points) == 0:
            return set()

        ids, etas, distances_m2 = points.candidates(point, radius)
        is_match = distances_m2 <= radius**2
        if max_eta is not None:
            is_match &= etas <= max_eta
        return set(ids[is_match].tolist())
