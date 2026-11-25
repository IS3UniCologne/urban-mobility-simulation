"""Tests for hexagon geometry in GeodesicEnvironment."""

import h3
import numpy as np
import pytest
from shapely.geometry import Polygon

from simulation.environment.geodesic_environment import GeodesicEnvironment

pytestmark = pytest.mark.unit


def test_random_position_lies_in_the_h3_cell() -> None:
    # at resolution 2 the flat polygon and the h3 cell differ often enough to catch
    cell = h3.latlng_to_cell(41.88, -87.63, 2)
    env = GeodesicEnvironment.__new__(GeodesicEnvironment)
    env._rng = np.random.default_rng(0)
    env._hex_geom_cache = {
        "hex": {cell: Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(cell)])}
    }

    for _ in range(2000):
        lat, lng = env.get_random_position(cell)
        assert h3.latlng_to_cell(lat, lng, 2) == cell
