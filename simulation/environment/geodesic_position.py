from __future__ import annotations  # noqa: D100

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

from simulation.environment.position import RegionId

from .position import Position

if TYPE_CHECKING:
    from shapely import Geometry

    from simulation.context.simulation_context import SimulationContext


class GeodesicPosition(Position):  # noqa: D101
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

        # Resolution 0 is the default resolution
        self._hex_id_by_resolution[self._default_resolution] = default_res_hex_id
        self._geometry = Point(self._lng, self._lat)

    def getExactLocation(self, geojson: bool = False) -> tuple[float, float]:  # noqa: D102
        if geojson:
            return (self._lng, self._lat)
        else:
            return (self._lat, self._lng)

    @property
    def geometry(self) -> Point:  # noqa: D102
        return self._geometry

    def __str__(self) -> str:  # noqa: D105
        return f"Latitude {self._lat} : Longitude {self._lng}"

    # ==
    def __eq__(self, other: object) -> bool:
        """
        Test equality of two GeodesicPositions
        :param other: GeodesicPosition
        :return: bool
        """  # noqa: D205, D400
        if not isinstance(other, GeodesicPosition):
            return NotImplemented
        else:
            return self._lat == other._lat and self._lng == other._lng

    # >>
    def __rshift__(self, other: GeodesicPosition) -> float:
        """
        Calculate haversine distance between two positions
        :param other: GeodesicPosition
        :return: Haversine distance in meter.
        """  # noqa: D205
        return haversine((self._lat, self._lng), (other._lat, other._lng), Unit.METERS)

    # <<
    def __lshift__(self, other: GeodesicPosition) -> float:
        """
        Calculate euclidean distance between two positions.

        This is a fast approximation of the haversine distance.
        In testing it was about 7.5x faster than the haversine distance calculation.
        Error is about 0.1% for distances of 10km, slowly increasing with distance.

        Benchmarks can be found in benchmarks/bench_geodesic_position.py

        Parameters
        ----------
        other : GeodesicPosition
            The other position to calculate the distance to.
        Returns
        -------
        float
            The euclidean distance in meters.
        """  # noqa: D202, D410, D411

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
            H3 Resolution. If None, uses the default resolution.

        Returns
        -------
        RegionId
            The hexagon ID for this position.
        """
        if resolution is None:
            resolution = self._default_resolution

        if resolution not in self._hex_id_by_resolution:
            self._hex_id_by_resolution[resolution] = self._compute_hex_id(resolution)

        return RegionId(self._hex_id_by_resolution[resolution])

    def is_in_geometry(self, geometry: Geometry) -> bool:  # noqa: D102
        if self._geometry.intersects(geometry):
            return True
        else:
            return False

    def difference(self, other: GeodesicPosition):  # noqa: ANN201
        """
        This function is meant for getting the full distance vector of the (lat, lng) coordinate system
        of two GeodesicPositions. This might not be vastly intelligent in terms of what the result means geographically
        but it is needed for constructing states for public vehicle agents.

        :param other: GeodesicPosition
        :return: returns a tuple of (self.lat - other.lat, self.lon - other.lon)
        """  # noqa: D205, D401, D404
        return tuple(
            x - y for x, y in zip(self.getExactLocation(), other.getExactLocation())
        )
