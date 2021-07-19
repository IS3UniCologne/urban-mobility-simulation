from numpy import random
import numpy

from shapely.geometry import Point
from simulation.environment.environment import Environment

class GeodesicEnvironment(Environment):

    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def getInstance():
        """ Static access method. """
        if GeodesicEnvironment.__instance == None:
            GeodesicEnvironment()
        return GeodesicEnvironment.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if GeodesicEnvironment.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            GeodesicEnvironment.__instance = self
            super(GeodesicEnvironment, self).__init__()
            self._random = numpy.random.RandomState(42) # use fnc reset_rnd_gen to change seed

    def getLayer(self, layer_name):
        """
            Return layer
        :param layer_name: GeoDataFrame containing all spatial elements of that layer
        :return:
        """
        return self.layer[layer_name]

    def addLayer(self, layer_name, layer):
        """
        Add a new layer to the environment. Typically, we assume a natural ordering of the layers (i.e., first layer is finest)
        :param layer_name: Layer name
        :param layer: Layer object stored as a Geopandas DataFrame
        :return:
        """
        self.layer[layer_name] = layer

    def get_random_position(self, hex_id, layer_name="hex_7"):
        """
        Returns a random position within given hexagon
        :param hex_id: Hexagon ID
        :param layer_name: Layername (i.e., resolution)
        :return: Random Point (Lat, Lng)
        """
        # Select Layer
        gdf = self.layer[layer_name]

        # Select Hexagon
        geometry = gdf.loc[hex_id].geometry

        # Sample random point within hexagon
        minx, miny, maxx, maxy = geometry.bounds
        points = []
        while len(points) < 1:
            y = self._random.uniform(minx, maxx)
            pnt = Point(self._random.uniform(minx, maxx), self._random.uniform(miny, maxy))
            if geometry.contains(pnt):
                return pnt.y, pnt.x # Latitude, Longitude


    def get_centroid(self, hex_id, layer_name="hex_7"):
        """
        Get centroid of hexagon
        :param hex_id: Hexagon ID
        :param layer_name: Layername (i.e., resolution, hex_7, hex_8, hex_9)
        :return: Point (lat,lng) representing centroid of hexagon
        """
        # Select Layer
        gdf = self.layer[layer_name]

        # Get geometry of hexagon
        geometry = gdf.loc[hex_id].geometry

        return geometry.centroid.y, geometry.centroid.x # Lat, Lng


    def get_hexagon(self, hex_id, layer_name = "hex_7"):
        """
        Get geometry of hexagon
        :param hex_id: Hexagon ID
        :param layer_name: Layername (i.e., resolution, hex_7, hex_8, hex_9)
        :return: Polygon (lat,lng) representing hexagon
        """

        # Select Layer
        gdf = self.layer[layer_name]

        # Get geometry of hexagon
        geometry = gdf.loc[hex_id].geometry

        return geometry # Hexagon Geometry

    def reset_random_generator(self, seed = 42):
        self._random = numpy.random.RandomState(seed)