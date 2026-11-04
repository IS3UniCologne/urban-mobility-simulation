"""Helper class to load or calculate distance matrix between hexagon centroids."""

import hashlib
from pathlib import Path

import h3
import pandas as pd
from haversine import Unit, haversine_vector

from simulation.helper.cache import write_cache


class DistanceMatrixImporter:
    """Load or calculate the distance matrix between hexagon centroids.

    Distance between hexagon elements are computed using haversine distances.
    """

    __slots__ = ("_cache_dir", "_hexagons", "_resolution")

    def __init__(self, hexagons: list[str], resolution: int, cache_dir: Path) -> None:
        self._hexagons = hexagons
        self._resolution = resolution
        self._cache_dir = Path(cache_dir)

    def load_distance_matrix(self) -> pd.DataFrame:
        """Load or calculate distance matrix between hexagon elements.

        Returns
        -------
        pd.DataFrame
            Square DataFrame indexed and columned by hex IDs with haversine
            distances in metres.
        """
        cache_path = self._cache_path()

        if cache_path.exists():
            return pd.read_parquet(cache_path)

        hexagon_centers = [h3.cell_to_latlng(x) for x in self._hexagons]
        distance_matrix = pd.DataFrame(
            haversine_vector(
                hexagon_centers, hexagon_centers, comb=True, unit=Unit.METERS
            ),
            index=self._hexagons,
            columns=self._hexagons,
        )

        write_cache(distance_matrix, cache_path)
        return distance_matrix

    def _cache_path(self) -> Path:
        cache_key = hashlib.sha256(
            ",".join(sorted(self._hexagons)).encode() + str(self._resolution).encode()
        ).hexdigest()[:12]
        return (
            self._cache_dir
            / f"{cache_key}_res{self._resolution}_distance_matrix.parquet"
        )
