"""Tests for the demand file validation of DemandImporter."""

from pathlib import Path

import h3
import pandas as pd
import pytest

from simulation.helper.enums import (
    DailyResolution,
    SpatialResolution,
    TemporalResolution,
)
from simulation.world.demand import demand_schema
from simulation.world.demand.demand_importer import DemandImporter

_ORIGIN, _OTHER_ORIGIN, *_DESTINATIONS = (
    h3.latlng_to_cell(lat, lng, SpatialResolution.HEX_8.value)
    for lat, lng in [(50.94, 6.96), (50.96, 6.98), (50.93, 6.95), (50.95, 6.97)]
)


def _write_demand(directory: Path, rates_of_first_slice: list[float]) -> Path:
    """Write a demand file of four slices, the first with the given rate per destination.

    Each other slice differs from the first in one key column only and carries its own rate.
    """
    slices = [
        (_ORIGIN, 0, False, rates_of_first_slice),
        (_ORIGIN, 1, False, [3.0, 3.0]),
        (_ORIGIN, 0, True, [4.0, 4.0]),
        (_OTHER_ORIGIN, 0, False, [5.0, 5.0]),
    ]
    rows = [
        {
            demand_schema.ORIGIN: slice_origin,
            demand_schema.DESTINATION: destination,
            demand_schema.TIME_BUCKET: bucket,
            demand_schema.IS_WEEKEND: is_weekend,
            demand_schema.ORIGIN_ARRIVAL_RATE: rate,
            demand_schema.DESTINATION_PROBABILITY: 0.5,
        }
        for slice_origin, bucket, is_weekend, rates in slices
        for destination, rate in zip(_DESTINATIONS, rates, strict=True)
    ]
    demand_path = directory / "demand.parquet"
    pd.DataFrame(rows).to_parquet(demand_path, index=False)
    return demand_path


@pytest.fixture
def importer() -> DemandImporter:
    """Return an importer for twelve-hour buckets at H3 resolution 8."""
    return DemandImporter(
        temporal_resolution=TemporalResolution.TWELVE_HOURLY_BUCKETS,
        spatial_resolution=SpatialResolution.HEX_8,
        daily_resolution=DailyResolution.DAILY,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "rates",
    [[2.0, 1.0], [0.0, 2.0], [float("nan"), 2.0]],
    ids=["two_rates", "zero_beside_positive", "missing_beside_positive"],
)
def test_load_rejects_origin_with_two_arrival_rates_in_one_slice(
    importer: DemandImporter, tmp_path: Path, rates: list[float]
) -> None:
    """Test that load rejects destinations of one slice with different arrival rates."""
    offending_slice = (
        f"{demand_schema.ORIGIN}={_ORIGIN}, "
        f"{demand_schema.TIME_BUCKET}=0, {demand_schema.IS_WEEKEND}=False"
    )
    with pytest.raises(
        ValueError,
        match=rf"^{demand_schema.ORIGIN_ARRIVAL_RATE} .* 1 .* e\.g\. {offending_slice}$",
    ):
        importer.load(_write_demand(tmp_path, rates))


@pytest.mark.unit
def test_load_accepts_one_arrival_rate_per_slice(
    importer: DemandImporter, tmp_path: Path
) -> None:
    """Test that load accepts one arrival rate per slice, whatever rate the other slices carry."""
    demand = importer.load(_write_demand(tmp_path, [2.0, 2.0]))

    assert len(demand) == 8
