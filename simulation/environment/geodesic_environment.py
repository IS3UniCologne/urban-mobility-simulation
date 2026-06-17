"""Geodesic spatial environment backed by H3 hexagons and GeoDataFrame layers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol, cast

import geopandas as gpd
import h3
import numpy
from shapely.geometry import Point, Polygon

from simulation.environment.environment import Environment

if TYPE_CHECKING:
    from collections.abc import Iterable

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle


class _Demand(Protocol):
    """Structural type for a demand with origin and destination positions."""

    origin: GeodesicPosition
    destination: GeodesicPosition


class GeodesicEnvironment(Environment):
    """
    Spatial environment using H3 hexagon layers stored as GeoDataFrames.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context providing configuration, RNG, and logging.
    """

    __slots__ = ("_centroid_cache", "_hex_geom_cache", "_logger", "_rng", "_utm_epsg")

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__()

        self._rng: numpy.random.Generator = sim.random_manager.get_rng(
            component_name="GEOENV"
        )

        self._hex_geom_cache: dict[str, dict[str, Polygon]] = {}
        self._centroid_cache: dict[str, tuple[float, float]] = {}

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
        """UTM CRS EPSG code."""
        return self._utm_epsg

    def getLayer(self, layer_name: str) -> gpd.GeoDataFrame:
        """Return layer stored under layer_name."""
        return self.layer[layer_name]

    def addLayer(self, layer_name: str, layer: gpd.GeoDataFrame) -> None:
        """
        Store a spatial layer under a name.

        Layers are assumed to have a natural ordering (first added is finest
        resolution).

        Parameters
        ----------
        layer_name : str
            Name to store layer under.
        layer : geopandas.GeoDataFrame
            Layer geometries.
        """
        self.layer[layer_name] = layer

    # TODO: Hardcoded layer here is dangerous
    # TODO: initialize pool of positions for every region once, then draw from there instead for efficiency?
    def get_random_position(
        self, hex_id: str, layer_name: str = "hex_7"
    ) -> tuple[float, float]:
        """
        Sample a uniformly random position within given hexagon.

        Parameters
        ----------
        hex_id : str
            Hexagon ID.
        layer_name : str
            Layer (resolution) to look up.

        Returns
        -------
        tuple of float
            Random point as (latitude, longitude).
        """
        # Select Layer
        gdf = self.layer[layer_name]

        # Select Hexagon
        geometry = cast("Polygon", gdf.loc[hex_id].geometry)

        # Sample random point within hexagon
        minx, miny, maxx, maxy = geometry.bounds
        while True:
            pnt = Point(self._rng.uniform(minx, maxx), self._rng.uniform(miny, maxy))
            if geometry.contains(pnt):
                return pnt.y, pnt.x  # Latitude, Longitude

    def get_centroid(self, hex_id: str) -> tuple[float, float]:
        """
        Return hexagon centroid (cached).

        Parameters
        ----------
        hex_id : str
            Hexagon ID.

        Returns
        -------
        tuple of float
            Centroid as (latitude, longitude).
        """
        if hex_id not in self._centroid_cache:
            lat, lng = h3.cell_to_latlng(hex_id)
            self._centroid_cache[hex_id] = (lat, lng)

        return self._centroid_cache[hex_id]

    def is_in_layer(self, hex_id: str, layer_name: str = "hex_7") -> bool:
        """Return whether a hexagon exists in the layer."""
        return hex_id in self.layer[layer_name].index

    def get_hexagon(self, hex_id: str, layer_name: str = "hex_7") -> Polygon | None:
        """
        Return hexagon geometry via a cached lookup.

        Parameters
        ----------
        hex_id : str
            Hexagon ID.
        layer_name : str
            Layer name (e.g. "hex_7", "hex_8").

        Returns
        -------
        shapely.geometry.Polygon or None
            Hexagon geometry, or None if not in layer.
        """
        if layer_name not in self._hex_geom_cache:
            self._hex_geom_cache[layer_name] = cast(
                "dict[str, Polygon]", self.layer[layer_name]["geometry"].to_dict()
            )

        return self._hex_geom_cache[layer_name].get(hex_id, None)

    @staticmethod
    def move_in_layer(hex_id: str, movement: str) -> str:
        r"""
        Return neighbouring hexagon reached by a movement.

        Neighbour layout (Central Place Indexing)::

                 ___3___
              /           \
            /1/          \2\
                   0
            \5\          /6/
             \  ________  /
                   4

        The movement name ("up", "left", ...) only needs to consistently map to
        the same neighbour. We use Central Place Indexing (CPI) based on the
        Generalized Balanced Ternary (GBT) prefix code for aperture-7 grids,
        visualised above (see
        https://web.archive.org/web/20240703092509/https://webpages.sou.edu/~sahrk/sqspc/pubs/autocarto14.pdf
        and https://h3geo.org/docs/core-library/h3Indexing).

        Here, and only here the below mapping of "up", "down" etc is guaranteed to match the above visualization indices
        HINT: This does not map (pun intended) to hexagons on a map because hexagons (their ijk coordinates) are rotated
        in the Europe Icosahedron face, meaning up does rather go kind of down right...
        HINT: This does also not hold particularly well between resolutions - an agent that learned how to move in one
        resolution will not necessarily work well in another resolution...

        Because hexagon cells are not really regular in projected space, we cannot simply move e.g. edge length "to" one
        of the six directions. Rather we need to get all neighbors (unordered) and assign them to one of the six edges.
        We can do this by leveraging the binary index representation of a unidirectional edge between two h3 cells.
        Bits 5-7 indicate the edge 1-6.( see: https://h3geo.org/docs/core-library/h3Indexing#h3-unidirectional-edge-index)

        Parameters
        ----------
        hex_id : str
            Current hexagon ID.
        movement : str
            One of "UP", "DOWN", "UP_LEFT", "UP_RIGHT", "DOWN_LEFT", "DOWN_RIGHT".

        Returns
        -------
        str
            Hexagon ID after movement.
        """
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
    def corridor(start: str, end: str, buffer_radius: int) -> set[str]:
        """
        Return hexagons forming a corridor between two cells.

        Gives the straight line of hexagons between start and end (same
        resolution), plus a buffer around it when buffer_radius > 0.

        Parameters
        ----------
        start : str
            Start hexagon ID.
        end : str
            End hexagon ID.
        buffer_radius : int
            Buffer radius in hex-cells.

        Returns
        -------
        set of str
            Hexagon IDs in the corridor.
        """
        straight = h3.grid_path_cells(start, end)
        return {
            item
            for sublist in [h3.grid_disk(h, buffer_radius) for h in straight]
            for item in sublist
        }

    @staticmethod
    def filter_demands_by_area(
        demands: Iterable[_Demand], area: Polygon
    ) -> list[_Demand]:
        """
        Keep demands whose origin and destination both fall within an area.

        Parameters
        ----------
        demands : iterable of demand
            Demands, each with origin and destination positions.
        area : shapely.geometry.Polygon
            Area to filter against.

        Returns
        -------
        list of demand
            Demands fully contained in the area.
        """
        filtered = []
        for d in demands:
            if Point(d.origin.getExactLocation()).within(area) and Point(
                d.destination.getExactLocation()
            ).within(area):
                filtered.append(d)

        return filtered

    def filter_demands_by_direction(
        self, demands: Iterable[_Demand], vehicle: PublicTransitVehicle
    ) -> list[_Demand]:
        """Keep demands whose direction roughly aligns with a vehicle's route."""
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
    def direction_aligns(direction: float, target: float, degrees: float = 180) -> bool:
        """Return whether a direction lies within degrees of a target bearing.

        Parameters
        ----------
        direction : float
            Direction to check (in degrees).
        target : float
            Target bearing (in degrees).
        degrees : float, optional
            Range of degrees to check (default is 180).

        Returns
        -------
        bool
            Whether the direction lies within the specified range of the target bearing.
        """
        assert degrees < 360
        target_range = (target - (degrees / 2), target + (degrees / 2))
        target_norm = tuple(x % 360 for x in target_range)

        direction_norm = direction % 360

        if target_norm[0] > target_norm[1]:
            # +90° was above 360°
            return direction_norm >= target_norm[0] or direction_norm <= target_norm[1]
        return target_norm[0] <= direction_norm <= target_norm[1]

    @staticmethod
    def get_bearing(lat1: float, long1: float, lat2: float, long2: float) -> float:
        """Return the great-circle bearing from one coordinate to another.

        Parameters
        ----------
        lat1 : float
            Latitude of first point.
        long1 : float
            Longitude of first point.
        lat2 : float
            Latitude of second point.
        long2 : float
            Longitude of second point.

        Returns
        -------
        float
            Great-circle bearing (in degrees).
        """
        # great circle bearing without projection
        # from https://stackoverflow.com/a/64747209
        dLon = long2 - long1
        x = math.cos(math.radians(lat2)) * math.sin(math.radians(dLon))
        y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.cos(math.radians(dLon))
        brng = numpy.arctan2(x, y)
        brng = numpy.degrees(brng)

        return float(brng)
