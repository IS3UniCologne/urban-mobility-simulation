from __future__ import annotations

from typing import TYPE_CHECKING

from pyproj import Transformer
from rtree.index import Index

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.vehicle.ride_hailing_vehicle import Vehicle


class FastSpatialVehicleIndex:
    def __init__(self, utm_epsg: str) -> None:
        """
        Set up a fast (approximate) spatial index for radius lookups based on euclidean distance (in meters)

        Parameters
        ----------
        utm_epsg : str
            The UTM zone of the simulated city in EPSG reference. For Berlin e.g. it's "epsg:25832"
        """
        self._transformer = Transformer.from_crs(
            crs_from="epsg:4326", crs_to=utm_epsg, always_xy=True
        )
        self._rtree = Index()

    def insert(self, vehicle: Vehicle) -> None:
        x, y = self._transformer.transform(
            *vehicle.position.getExactLocation(geojson=True)
        )
        bounds = (x, y, x, y)
        self._rtree.insert(vehicle.id, bounds)

    def delete(self, vehicle: Vehicle) -> None:
        x, y = self._transformer.transform(
            *vehicle.position.getExactLocation(geojson=True)
        )
        bounds = (x, y, x, y)
        self._rtree.delete(vehicle.id, bounds)

    def radius_search(self, point: GeodesicPosition, radius: float) -> list[int]:
        """_summary_

        Parameters
        ----------
        point : GeodesicPosition
            The center point of the search
        radius : float
            The radius within which to search for vehicles (in meters)

        Returns
        -------
        list[int]
            Return a list of vehicle.id
        """
        qx, qy = self._transformer.transform(*point.getExactLocation(geojson=True))

        # this uses bounding box (square), not radius. Do second pass downstream
        bounds = (qx - radius, qy - radius, qx + radius, qy + radius)
        vehicles_in_bbox = set(
            self._rtree.intersection(bounds)
        )  # TODO: set is a workaround because hits are duplicated - fix this

        return vehicles_in_bbox

    def transform_point(self, point: GeodesicPosition) -> tuple[float, float]:
        return self._transformer.transform(*point.getExactLocation(geojson=True))
