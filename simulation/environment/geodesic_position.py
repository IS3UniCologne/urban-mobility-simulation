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

from simulation.environment.position import RegionId

from .position import Position

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext


class GeodesicPosition(Position):
    __slots__ = ("_geometry", "_hex_id_by_resolution", "_lat", "_lng")

    def __init__(
        self,
        sim: SimulationContext,
        latitude: float,
        longitude: float,
        default_res_hex_id: str | None = None,
    ) -> None:
        super().__init__()
        self._lat = latitude
        self._lng = longitude
        self._default_resolution = sim.config.world.SPATIAL_RESOLUTION
        self._hex_id_by_resolution = {}

        # Resolution 0 is the default resolution
        self._hex_id_by_resolution[self._default_resolution] = default_res_hex_id
        self._geometry = Point(self._lng, self._lat)

    def getExactLocation(self, geojson=False):  # noqa: ANN001, ANN201
        if geojson:
            return (self._lng, self._lat)
        else:
            return (self._lat, self._lng)

    @property
    def geometry(self) -> Point:
        return self._geometry

    def __str__(self) -> str:
        return f"Latitude {self._lat} : Longitude {self._lng}"

    # ==
    def __eq__(self, other):  # noqa: ANN001, ANN204
        """
        Test equality of two GeodesicPositions
        :param other: GeodesicPosition
        :return: bool
        """
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
        """
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
        """

        return cy_euclidean_distance(self._lat, self._lng, other._lat, other._lng)

    def _compute_hex_id(self, resolution: int) -> str:
        """Compute H3 hex ID for given resolution."""
        return h3.geo_to_h3(self._lat, self._lng, resolution)

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

    def is_in_geometry(self, geometry):  # noqa: ANN001, ANN201
        if self._geometry.intersects(geometry):
            return True
        else:
            return False
