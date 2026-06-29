"""Loader for the inter-hexagon haversine distance matrix."""

from pathlib import Path

import h3
import pandas as pd
from haversine import Unit, haversine_vector


class DistanceMatrixImporter:
    """Load or (re-)compute the haversine distance matrix between hexagons.

    Parameters
    ----------
    hexagons : list of str
        H3 hexagon identifiers.
    resolution : int
        H3 resolution of the hexagons.
    data_path : str or pathlib.Path
        Directory holding the cached matrix CSV.
    city : str
        City name, used in the cache filename.
    """

    __slots__ = ("_city", "_data_path", "_hexagons", "_resolution")

    def __init__(
        self, hexagons: list[str], resolution: int, data_path: str | Path, city: str
    ) -> None:
        self._hexagons = hexagons
        self._resolution = resolution
        self._data_path = data_path
        self._city = city

    def load_distance_matrix(self) -> pd.DataFrame:
        """Load the cached distance matrix, computing and caching it if absent.

        Returns
        -------
        pandas.DataFrame
            Square matrix of inter-hexagon distances in metres, indexed and
            columned by hexagon id.
        """
        filename = f"{self._city}_distance_matrix_hex_{self._resolution}.csv"
        p = Path(self._data_path, filename)
        hexagons = self._hexagons

        if p.exists():
            distance_matrix = pd.read_csv(p, index_col=0)
        else:
            hexagon_centers = [h3.cell_to_latlng(x) for x in hexagons]
            distance_matrix = pd.DataFrame(
                haversine_vector(
                    hexagon_centers, hexagon_centers, comb=True, unit=Unit.METERS
                ),
                index=hexagons,
                columns=hexagons,
            )
            distance_matrix.to_csv(p, index=True)

            # Below is the old, inefficient way of doing things
            # geo_env = GeodesicEnvironment.getInstance()

            # for idx_row, hex_row in enumerate(hexagons):
            #     for idx_col, hex_col in enumerate(hexagons):
            #         # Symmetry
            #         if idx_col > idx_row:
            #             lat, lng = geo_env.get_centroid(hex_row, f'hex_{self._resolution}')
            #             hex_row_pos = GeodesicPosition(lat, lng, hex_row)
            #
            #             lat, lng = geo_env.get_centroid(hex_col, f'hex_{self._resolution}')
            #             hex_col_pos = GeodesicPosition(lat, lng, hex_col)
            #
            #             distance = hex_row_pos >> hex_col_pos
            #
            #             distance_matrix[hex_row][hex_col] = distance
            #             distance_matrix[hex_col][hex_row] = distance
            #         elif idx_col == idx_row:
            #             distance_matrix[hex_row][hex_col] = 0.0

        return distance_matrix
