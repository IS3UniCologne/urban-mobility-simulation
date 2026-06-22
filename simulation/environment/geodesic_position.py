"""Geodesic (latitude/longitude) position backed by H3 hexagon indexing."""

from __future__ import annotations

import h3 as h3
from haversine import Unit, haversine
from shapely.geometry import Point

try:
    from simulation.environment.cython_ext.cy_geodesic import cy_euclidean_distance
except ImportError:
    raise ImportError(
        "Required cython dependency not found.\n"
        "Run `uv pip install -e .` to install all required packages."
    )

from typing import TYPE_CHECKING

from simulation.helper.types import RegionId

from .position import Position

if TYPE_CHECKING:
    from shapely import Geometry

    from simulation.context.simulation_context import SimulationContext


class GeodesicPosition(Position):
    """
    Position identified by latitude and longitude.

    Parameters
    ----------
    sim : SimulationContext
        Provides the default spatial resolution.
    latitude : float
        Latitude in degrees.
    longitude : float
        Longitude in degrees.
    default_res_hex_id : RegionId or None
        Pre-computed H3 hex id at the default resolution, if known.
    """

    __slots__ = ("_geometry", "_hex_id_by_resolution", "_lat", "_lng")

    def __init__(
        self,
        sim: SimulationContext,
        latitude: float,
        longitude: float,
        default_res_hex_id: RegionId | None = None,
    ) -> None:
        super().__init__()
        self._lat = latitude
        self._lng = longitude
        self._default_resolution = sim.config.world.SPATIAL_RESOLUTION
        self._hex_id_by_resolution = {}

        # store the hex_id if it's provided
        if default_res_hex_id is not None:
            self._hex_id_by_resolution[self._default_resolution] = default_res_hex_id

        self._geometry = Point(self._lng, self._lat)

    def getExactLocation(self, geojson: bool = False) -> tuple[float, float]:
        """
        Return exact coordinates.

        Parameters
        ----------
        geojson : bool
            If True, return (longitude, latitude) GeoJSON order; otherwise
            (latitude, longitude).

        Returns
        -------
        tuple of float
            Coordinate pair.
        """
        if geojson:
            return (self._lng, self._lat)
        else:
            return (self._lat, self._lng)

    @property
    def geometry(self) -> Point:
        """Shapely point geometry."""
        return self._geometry

    def __str__(self) -> str:
        """Human-readable latitude/longitude representation."""
        return f"Latitude {self._lat} : Longitude {self._lng}"

    # ==
    def __eq__(self, other: object) -> bool:
        """Test equality of two GeodesicPositions."""
        if not isinstance(other, GeodesicPosition):
            return NotImplemented
        else:
            return self._lat == other._lat and self._lng == other._lng

    # >>
    def __rshift__(self, other: Position) -> float:
        """
        Calculate haversine distance between two positions.

        Parameters
        ----------
        other : Position
            Position to measure to.

        Returns
        -------
        float
            Haversine distance in meters.
        """
        return haversine((self._lat, self._lng), other.getExactLocation(), Unit.METERS)

    # <<
    def __lshift__(self, other: GeodesicPosition) -> float:
        """
        Calculate euclidean distance between two positions.

        Fast approximation of the haversine distance: in testing about 7.5x
        faster, with error around 0.1% at 10 km, slowly increasing with
        distance. Benchmarks are in benchmarks/bench_geodesic_position.py.

        Parameters
        ----------
        other : GeodesicPosition
            Position to measure to.

        Returns
        -------
        float
            Euclidean distance in meters.
        """
        return cy_euclidean_distance(self._lat, self._lng, other._lat, other._lng)

    def _compute_hex_id(self, resolution: int) -> str:
        """Compute H3 hex ID for given resolution."""
        return h3.latlng_to_cell(self._lat, self._lng, resolution)

    def get_region_id(self, resolution: int | None = None) -> RegionId:
        """
        Return H3 hexagon index based on current position.

        Parameters
        ----------
        resolution : int or None
            H3 resolution. If None, uses the default resolution.

        Returns
        -------
        RegionId
            Hexagon ID.
        """
        if resolution is None:
            resolution = self._default_resolution

        if resolution not in self._hex_id_by_resolution:
            self._hex_id_by_resolution[resolution] = self._compute_hex_id(resolution)

        return RegionId(self._hex_id_by_resolution[resolution])

    def is_in_geometry(self, geometry: Geometry) -> bool:
        """Return whether this position intersects geometry."""
        if self._geometry.intersects(geometry):
            return True
        else:
            return False

    def difference(self, other: GeodesicPosition) -> tuple[float, ...]:
        """
        Return coordinate-wise difference to another position.

        Gives the (lat, lng) distance vector ``(self.lat - other.lat,
        self.lng - other.lng)``. This might not be vastly intelligent in terms of what the result means geographically
        but it is needed for constructing states for public vehicle agents.

        Parameters
        ----------
        other : GeodesicPosition
            Position to subtract.

        Returns
        -------
        tuple of float
            Per-coordinate difference.
        """
        return tuple(
            x - y for x, y in zip(self.getExactLocation(), other.getExactLocation())
        )
