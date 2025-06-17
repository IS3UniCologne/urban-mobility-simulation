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
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.position import RegionId

from ..helper.configuration.configuration import Configuration
from .position import Position


class GeodesicPosition(Position):
    __slots__ = (
        "_default_hexagon",
        "_geo_env",
        "_geometry",
        "_global_resolution",
        "_lat",
        "_lng",
    )

    def __init__(self, latitude, longitude, default_hexagon=None) -> object:  # noqa: ANN001
        super(GeodesicPosition, self).__init__()  # noqa: UP008
        self._lat = latitude
        self._lng = longitude

        self._default_hexagon = {}
        self._global_resolution = Configuration().world.SPATIAL_RESOLUTION.value

        Configuration().mode_choice_model.MODE_CHOICE_STRATEGY

        if default_hexagon is not None:
            self._default_hexagon[self._global_resolution] = default_hexagon

        self._geometry = Point(self._lng, self._lat)

        self._geo_env = GeodesicEnvironment.getInstance()

    def getExactLocation(self, geojson=False):  # noqa: ANN001, ANN201
        if geojson:
            return (self._lng, self._lat)
        else:
            return (self._lat, self._lng)

    @property
    def geometry(self):  # noqa: ANN201
        return self._geometry

    def __str__(self):  # noqa: ANN204
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
    def __rshift__(self, other) -> float:  # noqa: ANN001
        """
        Calculate haversine distance between two positions
        :param other: GeodesicPosition
        :return: Haversine distance in meter.
        """
        return haversine((self._lat, self._lng), (other._lat, other._lng), Unit.METERS)

    # <<
    def __lshift__(self, other: "GeodesicPosition") -> float:
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

    def get_region_id(self, resolution: int = 0) -> RegionId:
        """
        Return h3 hexagon index based on current position (lng, lat)
        :param resolution: H3 Resolution (res = 0 <=> default => use global setting)
        :return: hex_id:   RegionId
        """
        # If resolution is set to default, use global settings
        if resolution == 0:
            resolution = self._global_resolution

        try:
            hex = self._default_hexagon[resolution]
        except KeyError:
            hex = h3.latlng_to_cell(self._lat, self._lng, resolution)
            self._default_hexagon[resolution] = hex

        return RegionId(hex)

    def is_in_geometry(self, geometry):  # noqa: ANN001, ANN201
        if self._geometry.intersects(geometry):
            return True
        else:
            return False

    def difference(self, other: "GeodesicPosition"):  # noqa: ANN201
        """
        This function is meant for getting the full distance vector of the (lat, lng) coordinate system
        of two GeodesicPositions. This might not be vastly intelligent in terms of what the result means geographically
        but it is needed for constructing states for public vehicle agents.

        :param other: GeodesicPosition
        :return: returns a tuple of (self.lat - other.lat, self.lon - other.lon)
        """
        return tuple(
            x - y for x, y in zip(self.getExactLocation(), other.getExactLocation())
        )
