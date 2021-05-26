from shapely.geometry import Point

from .geodesic_environment import GeodesicEnvironment
from .position import Position
from haversine import haversine

class GeodesicPosition(Position):

    def __init__(self, latitude, longitude):
        super(GeodesicPosition, self).__init__()
        self._lat = latitude
        self._lng = longitude

        self._geometry = Point(self._lng, self._lat)

    def getExactLocation(self):
        return (self._lat, self._lng)

    @property
    def geometry(self):
        return self._geometry

    def __str__(self):
        return f'Latitude {self._lat} : Longitude {self._lng}'

    # >>
    def __rshift__(self, other):
        """
        Calculate haversine distance between two positions
        :param other: GeodesicPosition
        :return: Haversine distance in meter.
        """
        return haversine((self._lat, self._lng), (other._lat, other._lng))*1000 # in meter


    def get_hexagon(self, resolution=7):
        """
        Return h3 hexagon object based on current position (lng, lat)
        :param resolution: H3 Resolution
        :return: hex_id:   String
                 geometry: Hexagon geometry
        """
        import geopandas as gpd

        geo_env = GeodesicEnvironment.getInstance()

        layer = geo_env.getLayer(f'hex_{resolution}')

        point_gdf = gpd.GeoDataFrame([self._geometry], columns=["geometry"], crs="EPSG:4326")

        hexagon = gpd.sjoin(layer, point_gdf, how="inner", op='intersects')

        if hexagon.shape[0] == 0:
            raise Exception(f'Cannot find a hexagon for {self}.')
        elif hexagon.shape[0] > 1:
            raise Exception(f'Surprisingly there are more than one hexagons on resolution {resolution} for {self}.')

        hex_id = hexagon.iloc[0][f'hex_id_{resolution}']
        geometry = hexagon.iloc[0]['geometry']

        return hex_id, geometry

    def is_in_geometry(self, geometry):
        if self._geometry.intersects(geometry):
            return True
        else:
            return False