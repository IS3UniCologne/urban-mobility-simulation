"""Sampling regression tests against the original rejection sampler."""

import geopandas as gpd
import numpy
import pytest
from shapely import contains_xy
from shapely.geometry import Polygon

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.exceptions import HexagonNotFoundError


@pytest.mark.unit
@pytest.mark.parametrize("seed", [1, 43, 91235])
def test_cached_sampling_preserves_points_and_rng_state(seed: int) -> None:
    polygons = {
        "a": Polygon([(13.0, 52.0), (13.2, 52.0), (13.1, 52.1)]),
        "b": Polygon([(-0.1, -0.2), (0.3, -0.2), (0.1, 0.4)]),
    }
    env = GeodesicEnvironment.__new__(GeodesicEnvironment)
    env._layer = {
        "first": gpd.GeoDataFrame(
            geometry=list(polygons.values()), index=list(polygons)
        )
    }
    # A different layer with the same IDs must not share the sampling bounds.
    env.layer["second"] = env.layer["first"].copy()
    env.layer["second"]["geometry"] = env.layer["second"].translate(xoff=5)
    env._hex_geom_cache = {}
    env._sampling_cache = {}
    env._rng = numpy.random.default_rng(seed)
    reference = numpy.random.default_rng(seed)

    for i in range(1000):
        name = "first" if i % 3 else "second"
        hex_id = "a" if i % 2 else "b"
        geometry = env.layer[name].loc[hex_id, "geometry"]
        minx, miny, maxx, maxy = geometry.bounds
        while True:
            lng = reference.uniform(minx, maxx)
            lat = reference.uniform(miny, maxy)
            if contains_xy(geometry, lng, lat):
                break
        assert env.get_random_position(hex_id, name) == (lat, lng)

    assert env._rng.bit_generator.state == reference.bit_generator.state
    with pytest.raises(HexagonNotFoundError):
        env.get_random_position("missing", "first")
