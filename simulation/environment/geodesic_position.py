from typing import Tuple

import h3 as h3
from haversine import Unit, haversine
from shapely.geometry import Point, Polygon

from simulation.environment.geodesic_environment import GeodesicEnvironment

from ..helper.configuration.configuration import Configuration
from .position import Position


class GeodesicPosition(Position):
    def __init__(self, latitude, longitude, default_hexagon=None) -> object:
        super(GeodesicPosition, self).__init__()
        self._lat = latitude
        self._lng = longitude

        self._default_hexagon = {}
        self._global_resolution = Configuration().world.SPATIAL_RESOLUTION.value

        Configuration().mode_choice_model.MODE_CHOICE_STRATEGY

        if default_hexagon is not None:
            self._default_hexagon[self._global_resolution] = default_hexagon

        self._geometry = Point(self._lng, self._lat)

        self._geo_env = GeodesicEnvironment.getInstance()

    def getExactLocation(self, geojson=False):
        if geojson:
            return (self._lng, self._lat)
        else:
            return (self._lat, self._lng)

    @property
    def geometry(self):
        return self._geometry

    def __str__(self):
        return f"Latitude {self._lat} : Longitude {self._lng}"

    # ==
    def __eq__(self, other):
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
    def __rshift__(self, other):
        """
        Calculate haversine distance between two positions
        :param other: GeodesicPosition
        :return: Haversine distance in meter.
        """
        return haversine((self._lat, self._lng), (other._lat, other._lng), Unit.METERS)

    def get_hexagon(self, resolution=0, return_geom=True) -> Tuple[str, Polygon]:
        """
        Return h3 hexagon object based on current position (lng, lat)
        :param resolution: H3 Resolution (res = 0 <=> default => use global setting)
        :param return_geom: Boolean indicating if geometry should be returned, ATTENTION: slows down a lot
        :return: hex_id:   String
                 geometry: Hexagon geometry
        """

        # If resolution is set to default, use global settings
        if resolution == 0:
            resolution = self._global_resolution

        layer = self._geo_env.getLayer(f"hex_{resolution}")

        try:
            hex = self._default_hexagon[resolution]

        except KeyError:
            hex = h3.geo_to_h3(self._lat, self._lng, resolution)
            self._default_hexagon[resolution] = hex

        if return_geom:
            geometry = layer.loc[hex].geometry
        else:
            geometry = None
        return hex, geometry

    def is_in_geometry(self, geometry):
        if self._geometry.intersects(geometry):
            return True
        else:
            return False

    def difference(self, other: "GeodesicPosition"):
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
