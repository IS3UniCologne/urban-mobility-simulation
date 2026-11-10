"""Geodesic spatial environment backed by H3 hexagons and GeoDataFrame layers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import h3
from shapely import contains_xy

from simulation.environment.bounding_box import (
    load_or_infer_bounding_box,
    read_demand_hex_ids,
    read_supply_hex_ids,
    warn_hex_mismatches,
)
from simulation.environment.environment import Environment
from simulation.environment.hex_layer import load_or_build_hex_layer
from simulation.helper.exceptions import HexagonNotFoundError

if TYPE_CHECKING:
    import geopandas as gpd
    import numpy
    from shapely.geometry import Polygon

    from simulation.context.simulation_context import SimulationContext


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

        demand_hex_ids = read_demand_hex_ids(sim.config.path.demand)
        supply_hex_ids_by_path = read_supply_hex_ids(
            sim.config.all_supply_distribution_paths()
        )

        bbox_df = load_or_infer_bounding_box(
            sim.config.path.bounding_box,
            demand_hex_ids,
            supply_hex_ids_by_path,
            self._logger,
        )
        self._utm_epsg = f"epsg:{bbox_df.estimate_utm_crs().to_epsg()}"
        self.addLayer("bounding_box", bbox_df)

        hex_df = load_or_build_hex_layer(
            bbox_df=bbox_df,
            resolution=sim.config.world.SPATIAL_RESOLUTION.value,
            cache_dir=sim.config.path.cache_dir,
            logger=self._logger,
        )
        self.addLayer("hex", hex_df)

        warn_hex_mismatches(
            hex_df, demand_hex_ids, supply_hex_ids_by_path, self._logger
        )

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
    def get_random_position(
        self, hex_id: str, layer_name: str = "hex"
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

        Raises
        ------
        HexagonNotFoundError
            If the hexagon is not in the layer.
        """
        geometry = self.get_hexagon(hex_id, layer_name)
        minx, miny, maxx, maxy = geometry.bounds
        while True:
            lng = self._rng.uniform(minx, maxx)
            lat = self._rng.uniform(miny, maxy)
            if contains_xy(geometry, lng, lat):
                return lat, lng

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

    def get_hexagon(self, hex_id: str, layer_name: str = "hex_7") -> Polygon:
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
        shapely.geometry.Polygon
            Hexagon geometry.

        Raises
        ------
        HexagonNotFoundError
            If the hexagon is not in the layer.
        """
        if layer_name not in self._hex_geom_cache:
            self._hex_geom_cache[layer_name] = cast(
                "dict[str, Polygon]", self.layer[layer_name]["geometry"].to_dict()
            )

        geometry = self._hex_geom_cache[layer_name].get(hex_id)
        if geometry is None:
            raise HexagonNotFoundError(
                f"Hexagon {hex_id} is not in layer {layer_name}."
            )
        return geometry
