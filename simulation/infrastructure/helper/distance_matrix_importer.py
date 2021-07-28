from pathlib import Path

import pandas as pd

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition


class DistanceMatrixImporter:
    """
    Proxy Class for Distance Matrix. Either (Re-)Calculate, or load Matrix, if already existing

    Distance between hexagon elements are computed using euclidean distances
    """

    def __init__(self, hexagons, resolution, data_path):
        self._hexagons = hexagons
        self._resolution = resolution
        self._data_path = data_path

    def load_distance_matrix(self):
        """
        Load or calculate distance matrix between hexagon elements
        :return:
        """

        filename = f"distance_matrix_hex_{self._resolution}.csv"
        p = Path(self._data_path, filename)
        hexagons = self._hexagons

        if p.exists():
            distance_matrix = pd.read_csv(p, index_col = 0)
        else:
            distance_matrix = pd.DataFrame([], index=hexagons, columns=hexagons)

            geo_env = GeodesicEnvironment.getInstance()

            for idx_row, hex_row in enumerate(hexagons):
                for idx_col, hex_col in enumerate(hexagons):
                    # Symmtery
                    if idx_col > idx_row:
                        lat, lng = geo_env.get_centroid(hex_row)
                        hex_row_pos = GeodesicPosition(lat, lng, hex_row)

                        lat, lng = geo_env.get_centroid(hex_col)
                        hex_col_pos = GeodesicPosition(lat, lng, hex_col)

                        distance = hex_row_pos >> hex_col_pos

                        distance_matrix[hex_row][hex_col] = distance
                        distance_matrix[hex_col][hex_row] = distance
                    elif idx_col == idx_row:
                        distance_matrix[hex_row][hex_col] = 0.0

            distance_matrix.to_csv(p, index = True)

        return distance_matrix


