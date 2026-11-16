"""Tests for the demand profile index of DemandFactory."""

import numpy
import pandas as pd
import pytest

from simulation.world.demand import demand_schema
from simulation.world.demand.demand_factory import DemandFactory


@pytest.fixture
def profile() -> pd.DataFrame:
    """Return a demand profile with three slices with demand and one without."""
    return pd.DataFrame(
        {
            demand_schema.ORIGIN: ["a", "a", "a", "b", "b"],
            demand_schema.TIME_BUCKET: [0, 0, 1, 0, 0],
            demand_schema.IS_WEEKEND: [False, False, False, False, True],
            demand_schema.ORIGIN_ARRIVAL_RATE: [2.0, 2.0, 0.5, 0.0, 1.5],
            demand_schema.DESTINATION: ["x", "y", "x", "y", "y"],
            demand_schema.DESTINATION_PROBABILITY: [0.25, 0.75, 1.0, 1.0, 1.0],
        }
    )


@pytest.mark.unit
def test_index_matches_row_filter(profile: pd.DataFrame) -> None:
    """Each slice holds exactly the rows a boolean filter on the frame selects."""
    slices = DemandFactory._index_demand_profile(profile)

    assert set(slices) == {("a", 0, False), ("a", 1, False), ("b", 0, True)}
    for (origin, bucket, weekend), demand_slice in slices.items():
        rows = profile[
            (profile[demand_schema.ORIGIN] == origin)
            & (profile[demand_schema.TIME_BUCKET] == bucket)
            & (profile[demand_schema.IS_WEEKEND] == weekend)
        ]
        assert (
            demand_slice.arrival_rate == rows[demand_schema.ORIGIN_ARRIVAL_RATE].iloc[0]
        )
        assert demand_slice.destinations == list(rows[demand_schema.DESTINATION])
        numpy.testing.assert_array_equal(
            demand_slice.destination_probabilities,
            rows[demand_schema.DESTINATION_PROBABILITY].to_numpy(),
        )
