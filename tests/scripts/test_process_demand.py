"""Unit tests for the DemandProcessor class."""

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.process_demand import DemandProcessor
from simulation.world.demand import demand_schema


def make_synthetic_trip_data(tmp_path: Path) -> Path:
    """Create a minimal synthetic trip data CSV for testing."""

    # Minimal synthetic data: 2 days, 2 time buckets, 2 hexagons
    data = [
        # day 0, bucket 0
        {
            "date_start": "2024-01-01",
            "is_holiday": 0,
            "time_bucket_4h": 0,
            "h3_start_7": "A",
            "h3_end_7": "B",
            "id": 1,
        },
        {
            "date_start": "2024-01-01",
            "is_holiday": 0,
            "time_bucket_4h": 0,
            "h3_start_7": "A",
            "h3_end_7": "A",
            "id": 2,
        },
        # day 0, bucket 1
        {
            "date_start": "2024-01-01",
            "is_holiday": 0,
            "time_bucket_4h": 1,
            "h3_start_7": "A",
            "h3_end_7": "B",
            "id": 1,
        },
        {
            "date_start": "2024-01-01",
            "is_holiday": 0,
            "time_bucket_4h": 1,
            "h3_start_7": "A",
            "h3_end_7": "A",
            "id": 1,
        },
        # day 1, bucket 0
        {
            "date_start": "2024-01-02",
            "is_holiday": 1,
            "time_bucket_4h": 0,
            "h3_start_7": "A",
            "h3_end_7": "B",
            "id": 1,
        },
        {
            "date_start": "2024-01-02",
            "is_holiday": 1,
            "time_bucket_4h": 0,
            "h3_start_7": "A",
            "h3_end_7": "A",
            "id": 1,
        },
        # day 1, bucket 1
        {
            "date_start": "2024-01-02",
            "is_holiday": 1,
            "time_bucket_4h": 1,
            "h3_start_7": "A",
            "h3_end_7": "B",
            "id": 2,
        },
        {
            "date_start": "2024-01-02",
            "is_holiday": 1,
            "time_bucket_4h": 1,
            "h3_start_7": "A",
            "h3_end_7": "A",
            "id": 1,
        },
        # Add a second hexagon with complete coverage
        {
            "date_start": "2024-01-01",
            "is_holiday": 0,
            "time_bucket_4h": 0,
            "h3_start_7": "B",
            "h3_end_7": "A",
            "id": 1,
        },
        {
            "date_start": "2024-01-01",
            "is_holiday": 0,
            "time_bucket_4h": 1,
            "h3_start_7": "B",
            "h3_end_7": "A",
            "id": 1,
        },
        {
            "date_start": "2024-01-02",
            "is_holiday": 1,
            "time_bucket_4h": 0,
            "h3_start_7": "B",
            "h3_end_7": "A",
            "id": 1,
        },
        {
            "date_start": "2024-01-02",
            "is_holiday": 1,
            "time_bucket_4h": 1,
            "h3_start_7": "B",
            "h3_end_7": "A",
            "id": 1,
        },
    ]
    df = pd.DataFrame(data)
    csv_path = tmp_path / "trips.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def test_demand_processor_basic(tmp_path: Path) -> None:
    """Test basic functionality of DemandProcessor with synthetic trip data.

    This checks that the processor can read the data, compute the required columns,
    and normalize the origin-destination probabilities correctly."""
    csv_path = make_synthetic_trip_data(tmp_path)
    processor = DemandProcessor(
        origin_column="h3_start_7",
        destination_column="h3_end_7",
        temporal_column="time_bucket_4h",
        day_column="is_holiday",
    )
    result = processor.process_trip_data(csv_path)
    # Check required output columns (standardized names)
    required = {
        demand_schema.ORIGIN,
        demand_schema.DESTINATION,
        demand_schema.TIME_BUCKET,
        demand_schema.IS_WEEKEND,
        demand_schema.DESTINATION_PROBABILITY,
        demand_schema.ORIGIN_ARRIVAL_RATE,
    }
    assert required.issubset(result.columns)
    # Check that all (day, bucket, origin) groups sum to 1 for destination_probability
    grouped = result.groupby(
        [demand_schema.IS_WEEKEND, demand_schema.TIME_BUCKET, demand_schema.ORIGIN]
    )[demand_schema.DESTINATION_PROBABILITY].sum()
    np.testing.assert_allclose(np.array(grouped.values), 1.0, rtol=1e-6)
    # Check that origin_arrival_rate is not null
    assert result[demand_schema.ORIGIN_ARRIVAL_RATE].notnull().all()


def test_demand_processor_missing_od(tmp_path: Path) -> None:
    """Test handling of missing OD pairs in trip data.

    We modify the synthetic data to remove one OD pair and ensure
    that the processor fills in missing pairs with zeros and normalizes correctly.
    """

    # Remove one OD pair for a group, should fill with zero and normalize
    csv_path = make_synthetic_trip_data(tmp_path)
    df = pd.read_csv(filepath_or_buffer=csv_path)
    # Remove all trips from B to B
    df = df[~((df["h3_start_7"] == "B") & (df["h3_end_7"] == "B"))]
    new_csv = tmp_path / "trips_missing.csv"
    df.to_csv(new_csv, index=False)
    processor = DemandProcessor(
        origin_column="h3_start_7",
        destination_column="h3_end_7",
        temporal_column="time_bucket_4h",
        day_column="is_holiday",
    )
    result = processor.process_trip_data(new_csv)
    # All (day, time, origin) groups should still sum to 1
    grouped = result.groupby(
        [demand_schema.IS_WEEKEND, demand_schema.TIME_BUCKET, demand_schema.ORIGIN]
    )[demand_schema.DESTINATION_PROBABILITY].sum()
    np.testing.assert_allclose(np.array(grouped.values), 1.0, rtol=1e-6)
    # There should be rows for B->B, but with destination_probability==0
    mask = (result[demand_schema.ORIGIN] == "B") & (
        result[demand_schema.DESTINATION] == "B"
    )
    assert (result.loc[mask, demand_schema.DESTINATION_PROBABILITY] == 0).all()


def test_demand_processor_incomplete_hexagon(tmp_path: Path) -> None:
    """Test handling of incomplete hexagon coverage in trip data.

    We modify the synthetic data to remove all trips for one (day, bucket) for hexagon B,
    so that B should be filtered out in the final result.
    """

    # Remove all trips for one (day, bucket) for hexagon B, so B should be filtered out
    csv_path = make_synthetic_trip_data(tmp_path)
    df = pd.read_csv(csv_path)
    # Remove all B, is_holiday=1, time_bucket_4h=1
    df = df[
        ~(
            (df["h3_start_7"] == "B")
            & (df["is_holiday"] == 1)
            & (df["time_bucket_4h"] == 1)
        )
    ]
    new_csv = tmp_path / "trips_incomplete.csv"
    df.to_csv(new_csv, index=False)
    processor = DemandProcessor(
        origin_column="h3_start_7",
        destination_column="h3_end_7",
        temporal_column="time_bucket_4h",
        day_column="is_holiday",
    )
    result = processor.process_trip_data(new_csv)
    # B should not appear as origin
    assert not (result[demand_schema.ORIGIN] == "B").any()
    # A should still be present
    assert (result[demand_schema.ORIGIN] == "A").any()
