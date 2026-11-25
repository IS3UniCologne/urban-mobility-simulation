"""Tests for the demand profile index and the segment draw of DemandFactory."""

from unittest.mock import Mock

import numpy
import pandas as pd
import pytest
import simpy

from simulation.helper.configuration.configuration import (
    Configuration,
    PopulationConfig,
)
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


@pytest.mark.unit
@pytest.mark.parametrize(
    "proportions",
    [
        [1.0],
        [0.0, 1.0],
        [1.0, 0.0],
        [0.2, 0.3, 0.5],
        [0.1, 0.2, 0.7],
        [0.0, 0.25, 0.0, 0.75, 0.0],
    ],
)
@pytest.mark.parametrize("seed", [1, 43, 91235])
def test_segment_draw_matches_generator_choice(
    proportions: list[float],
    seed: int,
    profile: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The segment draw picks the same segment as Generator.choice from the same stream."""
    template = Configuration("tests/configurations/saturated_sm").population.SEGMENTS[0]
    population = PopulationConfig(
        SEGMENTS=[template.model_copy(update={"PROPORTION": p}) for p in proportions]
    )
    sim = Mock()
    sim.env = simpy.Environment()
    sim.config.world.TEMPORAL_RESOLUTION = 1
    sim.config.population = population
    sim.uid_manager.generate_uid.return_value = (0, "DemandFactory_0")
    sim.random_manager.get_rng.return_value = numpy.random.default_rng(seed)
    monkeypatch.setattr(DemandFactory, "_load_demand_profile", lambda self: profile)
    monkeypatch.setattr(DemandFactory, "_load_modifiers", lambda self: None)
    factory = DemandFactory(sim, Mock())
    reference = numpy.random.default_rng(seed)

    # A segment with proportion 1.0 must still consume a random draw, or every later draw of the stream shifts
    for _ in range(2048):
        expected = reference.choice(len(proportions), p=proportions)
        assert factory._select_segment_for_demand() is population.SEGMENTS[expected]

    assert factory._rng.bit_generator.state == reference.bit_generator.state
