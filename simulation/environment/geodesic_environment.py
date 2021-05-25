from numpy import random
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

        # Get geometry of hexagon
        if layer_name == "hex_7":
            geometry = gdf[gdf["hex_id_7"] == hex_id].geometry
        elif layer_name == "hex_8":
            geometry = gdf[gdf["hex_id_8"] == hex_id].geometry
        elif layer_name == "hex_9":
            geometry = gdf[gdf["hex_id_9"] == hex_id].geometry

        # Extract Polygon (Shapely) object
        geometry = geometry.iloc[0]

        # Sample random point within hexagon
        minx, miny, maxx, maxy = geometry.bounds
        points = []
        while len(points) < 1:
            y = random.uniform(minx, maxx)
            pnt = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
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
        if layer_name == "hex_7":
            geometry = gdf[gdf["hex_id_7"] == hex_id].geometry
        elif layer_name == "hex_8":
            geometry = gdf[gdf["hex_id_8"] == hex_id].geometry
        elif layer_name == "hex_9":
            geometry = gdf[gdf["hex_id_9"] == hex_id].geometry

        # Extract Polygon (Shapely) object
        geometry = geometry.iloc[0]

        return geometry.centroid.y, geometry.centroid.x # Lat, Lng

