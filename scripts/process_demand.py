r"""Tool for processing raw trip data into simulation-ready demand parquet.

Transforms raw trip CSV data into spatio-temporal demand estimates (Poisson arrival
rates and multinomial destination probabilities) and writes demand.parquet with
standardized column names ready for use by the simulation.

The defaults assume the raw CSV already uses the standardized column names
(``origin``, ``destination``, ``time_bucket``, ``is_weekend``). Use the
``--*-column`` flags to remap from legacy or third-party schemas.

Usage
-----
python scripts/process_demand.py \\
    --input data/raw/berlin_trips.csv \\
    --output data/datasets/berlin/demand.parquet
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from simulation.world.demand import demand_schema

logger = logging.getLogger(__name__)


class DemandProcessor:
    """
    Processes raw trip data into spatio-temporal demand estimates.

    Transforms mobility trip data into statistical models for arrival times (Poisson)
    and destination choices (multinomial) at specified spatial and temporal resolutions.
    Output always uses standardized column names regardless of input column names.
    """

    def __init__(
        self,
        origin_column: str,
        destination_column: str,
        temporal_column: str,
        day_column: str,
    ) -> None:
        """
        Initialize demand processor with input column mappings.

        Parameters
        ----------
        origin_column : str
            Column name for trip origin in raw data.
        destination_column : str
            Column name for trip destination in raw data.
        temporal_column : str
            Column name for temporal bucketing in raw data.
        day_column : str
            Column name for day classification (weekend vs. weekday) in raw data.
        """
        self._origin_column = origin_column
        self._destination_column = destination_column
        self._temporal_column = temporal_column
        self._day_column = day_column

    def process_trip_data(self, trip_data_path: Path) -> pd.DataFrame:
        """
        Process raw trip data into demand estimates.

        Parameters
        ----------
        trip_data_path : Path
            Path to CSV file containing raw trip data.

        Returns
        -------
        DataFrame
            Demand data with standardized columns as defined in
            simulation.world.demand.demand_schema.
        """
        logger.debug("Processing trip data from %s", trip_data_path)

        trip_data = pd.read_csv(trip_data_path)

        arrival_times = self._calculate_arrival_times(trip_data)
        destination_probs = self._calculate_destination_probabilities(
            trip_data, arrival_times
        )

        return self._merge_results(arrival_times, destination_probs)

    def _calculate_arrival_times(self, trip_data: pd.DataFrame) -> pd.DataFrame:
        date_column = "date_start"

        trip_counts = (
            trip_data.groupby(
                [
                    date_column,
                    self._day_column,
                    self._temporal_column,
                    self._origin_column,
                ]
            )
            .agg({"id": "count"})
            .reset_index()
        )

        arrival_times = (
            trip_counts.groupby(
                [self._day_column, self._temporal_column, self._origin_column]
            )
            .agg({"id": "mean"})
            .reset_index()
        )

        return self._filter_complete_coverage(arrival_times)

    def _filter_complete_coverage(self, arrival_times: pd.DataFrame) -> pd.DataFrame:
        unique_days = len(arrival_times[self._day_column].unique())
        unique_times = len(arrival_times[self._temporal_column].unique())
        expected_combinations = unique_days * unique_times

        coverage_counts = (
            arrival_times.groupby([self._origin_column])
            .agg({"id": "count"})
            .reset_index()
        )

        complete_hexagons = coverage_counts[
            coverage_counts["id"] == expected_combinations
        ][[self._origin_column]].copy()

        complete_hexagons = complete_hexagons.sort_values(by=[self._origin_column])
        complete_hexagons["key"] = 1

        return arrival_times.merge(
            complete_hexagons, on=self._origin_column, how="inner"
        )

    def _calculate_destination_probabilities(
        self, trip_data: pd.DataFrame, arrival_times: pd.DataFrame
    ) -> pd.DataFrame:
        date_column = "date_start"

        complete_hexagons = arrival_times[
            [self._origin_column, "key"]
        ].drop_duplicates()

        destination_counts = (
            trip_data.groupby(
                [
                    date_column,
                    self._day_column,
                    self._temporal_column,
                    self._origin_column,
                    self._destination_column,
                ]
            )
            .agg({"id": "count"})
            .reset_index()
        )

        complete_combinations = self._create_complete_combinations(
            trip_data, complete_hexagons, date_column
        )

        od_matrix = complete_combinations.merge(
            destination_counts,
            on=[
                date_column,
                self._day_column,
                self._temporal_column,
                self._origin_column,
                self._destination_column,
            ],
            how="left",
        )

        od_matrix["id"] = od_matrix["id"].fillna(0)

        return self._calculate_multinomial_probabilities(od_matrix)

    def _create_complete_combinations(
        self, trip_data: pd.DataFrame, complete_hexagons: pd.DataFrame, date_column: str
    ) -> pd.DataFrame:
        temporal_combinations = self._extract_temporal_combinations(
            trip_data, date_column
        )
        spatial_combinations = self._create_spatial_combinations(complete_hexagons)

        complete_combinations = temporal_combinations.merge(
            spatial_combinations, on="key"
        )
        return complete_combinations.drop(columns=["id_x", "id_y", "key"])

    def _extract_temporal_combinations(
        self, trip_data: pd.DataFrame, date_column: str
    ) -> pd.DataFrame:
        date_combinations = (
            trip_data.groupby([date_column, self._day_column])
            .agg({"id": "count"})
            .reset_index()
        )
        time_combinations = (
            trip_data.groupby([self._temporal_column])
            .agg({"id": "count"})
            .reset_index()
        )
        date_combinations["key"] = 1
        time_combinations["key"] = 1
        return date_combinations.merge(time_combinations, on="key")

    def _create_spatial_combinations(
        self, complete_hexagons: pd.DataFrame
    ) -> pd.DataFrame:
        origins = complete_hexagons.copy()
        destinations = complete_hexagons.copy().rename(
            columns={self._origin_column: self._destination_column}
        )
        return origins.merge(destinations, on="key")

    def _calculate_multinomial_probabilities(
        self, od_matrix: pd.DataFrame
    ) -> pd.DataFrame:
        daily_trips = (
            od_matrix.groupby(
                [
                    self._day_column,
                    self._temporal_column,
                    self._origin_column,
                    self._destination_column,
                ]
            )
            .agg({"id": "sum"})
            .reset_index()
            .rename(columns={"id": "total_trips"})
        )

        origin_totals = (
            daily_trips.groupby(
                [self._day_column, self._temporal_column, self._origin_column]
            )
            .agg({"total_trips": "sum"})
            .reset_index()
            .rename(columns={"total_trips": "origin_total"})
        )

        probability_estimates = daily_trips.merge(
            origin_totals,
            on=[self._day_column, self._temporal_column, self._origin_column],
            how="inner",
        )
        probability_estimates["prob"] = (
            probability_estimates["total_trips"] / probability_estimates["origin_total"]
        )
        return probability_estimates

    def _merge_results(
        self, arrival_times: pd.DataFrame, destination_probs: pd.DataFrame
    ) -> pd.DataFrame:
        result = destination_probs.merge(
            arrival_times,
            on=[self._day_column, self._temporal_column, self._origin_column],
            how="left",
        )

        columns_to_drop = ["key", "origin_total", "total_trips"]
        result = result.drop(
            columns=[col for col in columns_to_drop if col in result.columns],
            errors="ignore",
        )

        # Rename to standardized output column names
        result = result.rename(
            columns={
                self._origin_column: demand_schema.ORIGIN,
                self._destination_column: demand_schema.DESTINATION,
                self._temporal_column: demand_schema.TIME_BUCKET,
                self._day_column: demand_schema.IS_WEEKEND,
                "prob": demand_schema.DESTINATION_PROBABILITY,
                "id": demand_schema.ORIGIN_ARRIVAL_RATE,
            }
        )

        return result[
            [
                demand_schema.ORIGIN,
                demand_schema.DESTINATION,
                demand_schema.TIME_BUCKET,
                demand_schema.IS_WEEKEND,
                demand_schema.ORIGIN_ARRIVAL_RATE,
                demand_schema.DESTINATION_PROBABILITY,
            ]
        ]


def main() -> None:
    """CLI entrypoint for processing raw trip data."""
    parser = argparse.ArgumentParser(
        description="Process raw trip CSV into demand.parquet"
    )
    parser.add_argument(
        "--input", required=True, type=Path, help="Path to raw trip CSV"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Output demand.parquet path"
    )
    parser.add_argument(
        "--origin-column",
        default=demand_schema.ORIGIN,
        help="Origin column in raw data",
    )
    parser.add_argument(
        "--destination-column",
        default=demand_schema.DESTINATION,
        help="Destination column in raw data",
    )
    parser.add_argument(
        "--temporal-column",
        default=demand_schema.TIME_BUCKET,
        help="Temporal column in raw data",
    )
    parser.add_argument(
        "--day-column",
        default=demand_schema.IS_WEEKEND,
        help="Day type column in raw data",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    processor = DemandProcessor(
        origin_column=args.origin_column,
        destination_column=args.destination_column,
        temporal_column=args.temporal_column,
        day_column=args.day_column,
    )

    result = processor.process_trip_data(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(args.output, index=False)
    logger.info("Wrote %d rows to %s", len(result), args.output)


if __name__ == "__main__":
    main()
