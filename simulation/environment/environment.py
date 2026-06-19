"""Abstract spatial environment storing named map layers."""

from abc import ABC, abstractmethod

import geopandas as gpd


class Environment(ABC):
    """
    Abstract spatial environment storing named map layers.

    Concrete environments expose spatial layers (e.g. hexagon grids) as GeoDataFrames keyed by name.
    """

    # TODO: not really an ABC with init
    __slots__ = ("_layer",)

    def __init__(self) -> None:
        self._layer: dict[str, gpd.GeoDataFrame] = {}  # name: layer frame

    @property
    def layer(self) -> dict[str, gpd.GeoDataFrame]:
        """Mapping of layer name to its GeoDataFrame."""
        return self._layer

    @abstractmethod
    def getLayer(self, layer_name: str) -> gpd.GeoDataFrame:
        """Return layer stored under layer_name."""

    @abstractmethod
    def addLayer(self, layer_name: str, layer: gpd.GeoDataFrame) -> None:
        """Store layer under layer_name."""
