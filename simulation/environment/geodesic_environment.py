import math

import h3
from numpy import random
import numpy

import pyproj
from shapely.geometry import Point, Polygon
from simulation.environment.environment import Environment
from simulation.vehicle.vehicle import Vehicle


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

            self._geodesic = pyproj.Geod(ellps='WGS84')
            self._random = numpy.random.RandomState(42)  # use fnc reset_rnd_gen to change seed

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
                return pnt.y, pnt.x  # Latitude, Longitude

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

        return geometry.centroid.y, geometry.centroid.x  # Lat, Lng

    def is_in_layer(self, hex_id, layer_name="hex_7"):
        return hex_id in self.layer[layer_name].index

    def get_hexagon(self, hex_id, layer_name="hex_7"):
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

        return geometry  # Hexagon Geometry

    def reset_random_generator(self, seed=42):
        self._random = numpy.random.RandomState(seed)

    @staticmethod
    def move_in_layer(hex_id, movement):
        """
              ___3___
           /           \
         /1/          \2\
                0
         \5\          /6/
          \  ________  /
                4

        It doesn't really matter if the movement is named "up" or "left" as long as it corresponds always to the same
        neighbor of the hexagon cell. Here, we use the Central Place Indexing (CPI) based on the Generalized Balanced
        Ternary (GBT) prefix code system for aperture 7 grids, which is visualized above.

        (see:
        http://webpages.sou.edu/~sahrk/sqspc/pubs/autocarto14.pdf and https://h3geo.org/docs/core-library/h3Indexing)

        Here, and only here the below mapping of "up", "down" etc is guaranteed to match the above visualization indices
        HINT: This does not map (pun intended) to hexagons on a map because hexagons (their ijk coordinates) are rotated
        in the Europe Icosahedron face, meaning up does rather go kind of down right...
        HINT: This does also not hold particularly well between resolutions - an agent that learned how to move in one
        resolution will not necessarily work well in another resolution...

        Because hexagon cells are not really regular in projected space, we cannot simply move e.g. edge length "to" one
        of the six directions. Rather we need to get all neighbors (unordered) and assign them to one of the six edges.
        We can do this by leveraging the binary index representation of a unidirectional edge between two h3 cells.
        Bits 5-7 indicate the edge 1-6.( see: https://h3geo.org/docs/core-library/h3Indexing#h3-unidirectional-edge-index)

        :param hex_id: Current hex id
        :param movement: one of ["UP", "DOWN", "UP_LEFT", "UP_RIGHT", "DOWN_LEFT", "DOWN_RIGHT"]
        :return: hex id after "movement"
        """

        EDGE_MAPPING = {
            'UP': 3,
            'UP_RIGHT': 2,
            'DOWN_RIGHT': 6,
            'DOWN': 4,
            'DOWN_LEFT': 5,
            'UP_LEFT': 1
        }

        # create mapping of edge number -> neighbors
        neighbors = {
            int(f'{int(x, base=16) + 0x200:0>64b}'[5:8], base=2):
                h3.get_destination_h3_index_from_unidirectional_edge(x)
            for x in h3.get_h3_unidirectional_edges_from_hexagon(hex_id)
        }

        assert len(neighbors) == 6

        new_hex_id = neighbors[EDGE_MAPPING[movement]]

        # quick sanity check
        assert h3.h3_get_resolution(hex_id) == h3.h3_get_resolution(new_hex_id)
        assert h3.h3_indexes_are_neighbors(hex_id, new_hex_id) # should be neighbors
        assert h3.h3_get_faces(hex_id) == h3.h3_get_faces(new_hex_id) # should be on the same icosahedron face
        assert h3.h3_get_base_cell(hex_id) == h3.h3_get_base_cell(new_hex_id) # TODO: should be on the same base cell?

        return new_hex_id

    @staticmethod
    def corridor(start, end, k):
        """
        Given a start and end hexagon id (with same resolution), return a straight line of hexagons between them
        plus (optionally for k>0) a buffer of k hex-cells around it.

        :param start: start hexagon id
        :param end: end hexagon id
        :param k: k-hex buffer
        :return: set of hexagon ids
        """
        straight = h3.h3_line(start, end)
        return {item for sublist in [h3.k_ring(h, k) for h in straight] for item in sublist}

    @staticmethod
    def filter_demands_by_corridor(demands, corridor):
        """
        :param demands: [{origin: GeodesicPosition, destination: GeodesicPosition}, ...]
        :param corridor: set of hexagon cell ids
        :return: list of demands which have both origin and destination within the corridor
        """

        poly_corridor = Polygon(h3.h3_set_to_multi_polygon(corridor, geo_json=False)[0][0])

        filtered = []
        for d in demands:
            if (Point(d.origin.getExactLocation()).within(poly_corridor) and
                    Point(d.destination.getExactLocation()).within(poly_corridor)):
                filtered.append(d)

        return filtered

    def filter_demands_by_direction(self, demands, vehicle: Vehicle):
        route_direction, _, _ = self._geodesic.inv(*vehicle.position.getExactLocation(geojson=True),
                                             *vehicle.route.destination.getExactLocation(geojson=True))
        route_direction_range = (route_direction-90, route_direction+90)
        route_direction_norm = [(x+360)%360 for x in route_direction_range]

        filtered = []
        for d in demands:
            demand_direction, _, _ = self._geodesic.inv(*d.origin.getExactLocation(geojson=True),
                                                  *d.destination.getExactLocation(geojson=True))
            demand_direction_norm = (demand_direction + 360) % 360
            if route_direction_norm[0] > route_direction_norm[1]:
                # +90° was above 360°
                if demand_direction_norm >= route_direction_norm[0] or demand_direction_norm <= route_direction_norm[1]:
                    filtered.append(d)
            elif route_direction_norm[0] <= demand_direction_norm <= route_direction_norm[1]:
                filtered.append(d)

        return filtered
