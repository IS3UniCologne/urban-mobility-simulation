from __future__ import annotations  # noqa: D100

import math
from functools import cached_property
from typing import TYPE_CHECKING

import geopandas as gpd
import h3
import numpy as np
from shapely.geometry import Point, Polygon

from simulation.environment.environment import Environment

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.vehicle.vehicle import Vehicle


class GeodesicEnvironment(Environment):  # noqa: D101
    __slots__ = ("_centroid_cache", "_hex_geom_cache", "_logger", "_rng", "_utm_epsg", "__dict__")

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__()

        self._rng: np.random.Generator = sim.random_manager.get_rng(
            component_name="GEOENV"
        )

        self._hex_geom_cache = {}
        self._centroid_cache = {}

        self._logger = sim.log_manager.get_class_logger(self.__class__.__name__)

        # TODO Why are we reading all the files? One should be enough.
        # Read Environment Files
        with open(sim.config.path.PATH_ENV_BOUNDING_BOX, encoding="utf-8") as file:
            env_df = gpd.read_file(file)
            if env_df.crs is None:
                self._logger.warning(
                    "Bounding box CRS is None. Defaulting to EPSG:4326."
                )
                env_df.set_crs("epsg:4326", inplace=True)
            self._utm_epsg = f"epsg:{env_df.estimate_utm_crs().to_epsg()}"

        with open(sim.config.path.PATH_ENV_HEX_LAYER_RES_9, encoding="utf-8") as file:
            env_df_hex_9 = gpd.read_file(file)
            env_df_hex_9.set_index("hex_id_9", inplace=True)

        with open(sim.config.path.PATH_ENV_HEX_LAYER_RES_8, encoding="utf-8") as file:
            env_df_hex_8 = gpd.read_file(file)
            env_df_hex_8.set_index("hex_id_8", inplace=True)

        with open(sim.config.path.PATH_ENV_HEX_LAYER_RES_7, encoding="utf-8") as file:
            env_df_hex_7 = gpd.read_file(file)
            env_df_hex_7.set_index("hex_id_7", inplace=True)

        self.addLayer("bounding_box", env_df)
        self.addLayer("hex_9", env_df_hex_9)
        self.addLayer("hex_8", env_df_hex_8)
        self.addLayer("hex_7", env_df_hex_7)

    @property
    def utm_epsg(self) -> str:
        """The UTM CRS EPSG code for the environment."""
        return self._utm_epsg


    def getLayer(self, layer_name: str):  # noqa: ANN201
        """
            Return layer
        :param layer_name: GeoDataFrame containing all spatial elements of that layer
        :return:
        """  # noqa: D205, D400
        return self.layer[layer_name]

    def addLayer(self, layer_name, layer):  # noqa: ANN001, ANN201
        """
        Add a new layer to the environment. Typically, we assume a natural ordering of the layers (i.e., first layer is finest)
        :param layer_name: Layer name
        :param layer: Layer object stored as a Geopandas DataFrame
        :return:
        """  # noqa: D205, D400
        self.layer[layer_name] = layer

    # TODO: Hardcoded layer here is dangerous
    # TODO: initialize pool of positions for every region once, then draw from there instead for efficiency?
    def get_random_position(
        self, hex_id: str, layer_name: str = "hex_7"
    ) -> tuple[float, float]:
        """
        Returns a random position within given hexagon
        :param hex_id: Hexagon ID
        :param layer_name: Layername (i.e., resolution)
        :return: Random Point (Lat, Lng)
        """  # noqa: D205, D400, D401
        # Select Layer
        gdf = self.layer[layer_name]

        # Select Hexagon
        geometry = gdf.loc[hex_id].geometry

        # Sample random point within hexagon
        minx, miny, maxx, maxy = geometry.bounds
        points = []
        while len(points) < 1:
            pnt = Point(self._rng.uniform(minx, maxx), self._rng.uniform(miny, maxy))
            if geometry.contains(pnt):
                return pnt.y, pnt.x  # Latitude, Longitude



    def get_centroid(self, hex_id: str) -> tuple[float, float]:
        """
        Get centroid of hexagon, results are cached for performance
        :param hex_id: Hexagon ID
        :param layer_name: Layername (i.e., resolution, hex_7, hex_8, hex_9)
        :return: Point (lat,lng) representing centroid of hexagon
        """  # noqa: D205, D400
        if hex_id not in self._centroid_cache:
            lat, lng = h3.cell_to_latlng(hex_id)
            self._centroid_cache[hex_id] = (lat, lng)

        return self._centroid_cache[hex_id]

    def is_in_layer(self, hex_id, layer_name="hex_7"):  # noqa: ANN001, ANN201, D102
        return hex_id in self.layer[layer_name].index

    def get_hexagon(self, hex_id, layer_name="hex_7"):  # noqa: ANN001, ANN201
        """
        Get geometry of hexagon with optimized lookup.
        :param hex_id: Hexagon ID
        :param layer_name: Layer name (e.g., "hex_7", "hex_8").
        :return: Polygon representing the hexagon
        """  # noqa: D202, D205, D400

        if layer_name not in self._hex_geom_cache:
            self._hex_geom_cache[layer_name] = self.layer[layer_name][
                "geometry"
            ].to_dict()

        return self._hex_geom_cache[layer_name].get(hex_id, None)


    @staticmethod
    def move_in_layer(hex_id: str, movement: str) -> str:
        """
              ___3___
           /           \
         /1/          \2\
                0
         \\5\\          /6/
          \\  ________  /
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
        """  # noqa: D202, D205, D301, D400

        EDGE_MAPPING = {
            "UP": 3,
            "UP_RIGHT": 2,
            "DOWN_RIGHT": 6,
            "DOWN": 4,
            "DOWN_LEFT": 5,
            "UP_LEFT": 1,
        }

        # create mapping of edge number -> neighbors
        neighbors = {
            int(
                f"{int(x, base=16) + 0x200:0>64b}"[5:8], base=2
            ): h3.get_directed_edge_destination(x)
            for x in h3.origin_to_directed_edges(hex_id)
        }

        assert len(neighbors) == 6

        new_hex_id = neighbors[EDGE_MAPPING[movement]]

        # quick sanity check
        assert h3.get_resolution(hex_id) == h3.get_resolution(new_hex_id)
        assert h3.are_neighbor_cells(hex_id, new_hex_id)  # should be neighbors
        assert h3.get_icosahedron_faces(hex_id) == h3.get_icosahedron_faces(
            new_hex_id
        )  # should be on the same icosahedron face
        assert h3.get_base_cell_number(hex_id) == h3.get_base_cell_number(
            new_hex_id
        )  # TODO: should be on the same base cell?

        return new_hex_id

    @staticmethod
    def corridor(start: str, end: str, k: int) -> set[str]:
        """
        Given a start and end hexagon id (with same resolution), return a straight line of hexagons between them
        plus (optionally for k>0) a buffer of k hex-cells around it.

        :param start: start hexagon id
        :param end: end hexagon id
        :param k: k-hex buffer
        :return: set of hexagon ids
        """  # noqa: D205
        straight = h3.grid_path_cells(start, end)
        return {
            item
            for sublist in [h3.grid_disk(h, k) for h in straight]
            for item in sublist
        }

    @staticmethod
    def filter_demands_by_area(demands, area: Polygon):  # noqa: ANN001, ANN205
        """
        :param demands: [{origin: GeodesicPosition, destination: GeodesicPosition}, ...]
        :param area: shapely.Polygon
        :return: list of demands which have both origin and destination within the area
        """  # noqa: D202, D205

        filtered = []
        for d in demands:
            if Point(d.origin.getExactLocation()).within(area) and Point(
                d.destination.getExactLocation()
            ).within(area):
                filtered.append(d)

        return filtered

    def filter_demands_by_direction(self, demands, vehicle: Vehicle):  # noqa: ANN001, ANN201, D102
        route_direction = self.get_bearing(
            *vehicle.position.getExactLocation(),
            *vehicle.route.destination.getExactLocation(),
        )
        route_direction_range = (route_direction - 90, route_direction + 90)
        route_direction_norm = [(x + 360) % 360 for x in route_direction_range]

        filtered = []
        for d in demands:
            # TODO: parallelize?
            demand_direction = self.get_bearing(
                *d.origin.getExactLocation(), *d.destination.getExactLocation()
            )
            demand_direction_norm = (demand_direction + 360) % 360
            if route_direction_norm[0] > route_direction_norm[1]:
                # +90° was above 360°
                if (
                    demand_direction_norm >= route_direction_norm[0]
                    or demand_direction_norm <= route_direction_norm[1]
                ):
                    filtered.append(d)
            elif (
                route_direction_norm[0]
                <= demand_direction_norm
                <= route_direction_norm[1]
            ):
                filtered.append(d)

        return filtered

    @staticmethod
    def direction_aligns(direction, target, degrees=180) -> bool:  # noqa: ANN001, D102
        assert degrees < 360
        target_range = (target - (degrees / 2), target + (degrees / 2))
        target_norm = tuple(x % 360 for x in target_range)

        direction_norm = direction % 360

        if target_norm[0] > target_norm[1]:
            # +90° was above 360°
            if direction_norm >= target_norm[0] or direction_norm <= target_norm[1]:
                return True
        elif target_norm[0] <= direction_norm <= target_norm[1]:
            return True
        else:
            return False

    @staticmethod
    def get_bearing(lat1, long1, lat2, long2):  # noqa: ANN001, ANN205, D102
        # great circle bearing without projection
        # from https://stackoverflow.com/a/64747209
        dLon = long2 - long1
        x = math.cos(math.radians(lat2)) * math.sin(math.radians(dLon))
        y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.cos(math.radians(dLon))
        brng = np.arctan2(x, y)
        brng = np.degrees(brng)

        return brng