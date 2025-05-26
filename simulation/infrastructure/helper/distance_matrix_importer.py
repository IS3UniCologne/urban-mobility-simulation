from pathlib import Path

import h3
import pandas as pd
from haversine import Unit, haversine_vector


class DistanceMatrixImporter:
    """
    Proxy Class for Distance Matrix. Either (Re-)Calculate, or load Matrix, if already existing

    Distance between hexagon elements are computed using haversine distances
    """

    __slots__ = ("_city", "_data_path", "_hexagons", "_resolution")

    def __init__(self, hexagons, resolution, data_path, city):
        self._hexagons = hexagons
        self._resolution = resolution
        self._data_path = data_path
        self._city = city

    def load_distance_matrix(self):
        """
        Load or calculate distance matrix between hexagon elements
        :return:
        """

        filename = f"{self._city}_distance_matrix_hex_{self._resolution}.csv"
        p = Path(self._data_path, filename)
        hexagons = self._hexagons

        if p.exists():
            distance_matrix = pd.read_csv(p, index_col=0)
        else:
            hexagon_centers = [h3.h3_to_geo(x) for x in hexagons]
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
