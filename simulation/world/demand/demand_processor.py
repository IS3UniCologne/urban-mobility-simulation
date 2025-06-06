"""Processes raw trip data into spatio-temporal demand estimates using statistical models."""

import logging
from pathlib import Path

import pandas as pd


class DemandProcessor:
    """
    Processes raw trip data into spatio-temporal demand estimates.

    Transforms mobility trip data into statistical models for arrival times (Poisson)
    and destination choices (multinomial) at specified spatial and temporal resolutions.
    """

    def __init__(
        self, spatial_columns: tuple[str, str], temporal_column: str, day_column: str
    ) -> None:
        """
        Initialize demand processor with column mappings.

        Parameters
        ----------
        spatial_columns : tuple of str
            Origin and destination column names for spatial resolution
        temporal_column : str
            Column name for temporal bucketing
        day_column : str
            Column name for day classification (e.g., holiday indicator)
        """
        self._origin_column, self._destination_column = spatial_columns
        self._temporal_column = temporal_column
        self._day_column = day_column

    def process_trip_data(self, trip_data_path: Path) -> pd.DataFrame:
        """
        Process raw trip data into demand estimates.

        Parameters
        ----------
        trip_data_path : Path
            Path to CSV file containing raw trip data

        Returns
        -------
        DataFrame
            Processed demand data with statistical models for arrival times
            and destination probabilities
        """
        logging.debug(
            "Processing trip data from %s",
            trip_data_path,
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

        trip_data = pd.read_csv(trip_data_path)

        arrival_times = self._calculate_arrival_times(trip_data)
        destination_probs = self._calculate_destination_probabilities(
            trip_data, arrival_times
        )

        return self._merge_results(arrival_times, destination_probs)

    def _calculate_arrival_times(self, trip_data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Poisson arrival rates for each spatio-temporal cell.

        Estimates lambda parameters for Poisson distributions representing
        trip arrival rates in each spatial-temporal-daily combination.

        Parameters
        ----------
        trip_data : DataFrame
            Raw trip data with required columns for grouping

        Returns
        -------
        DataFrame
            Arrival time estimates with columns for spatial, temporal, and
            daily dimensions plus Poisson rate estimates
        """
        date_column = "date_start"

        # Count trips by spatio-temporal resolution
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

        # Calculate mean arrival rates (Poisson lambda estimates)
        arrival_times = (
            trip_counts.groupby(
                [self._day_column, self._temporal_column, self._origin_column]
            )
            .agg({"id": "mean"})
            .reset_index()
        )

        # Filter for complete temporal coverage
        filtered_arrival_times = self._filter_complete_coverage(arrival_times)

        logging.debug(
            "Calculated arrival times for %d spatio-temporal cells",
            len(filtered_arrival_times),
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

        return filtered_arrival_times

    def _filter_complete_coverage(self, arrival_times: pd.DataFrame) -> pd.DataFrame:
        """
        Filter hexagons that have data for all temporal combinations.

        Ensures statistical reliability by only including spatial units with
        complete temporal coverage across all day types and time buckets.

        Parameters
        ----------
        arrival_times : DataFrame
            Raw arrival time estimates

        Returns
        -------
        DataFrame
            Filtered arrival times with complete temporal coverage
        """
        # Calculate expected number of temporal combinations
        unique_days = len(arrival_times[self._day_column].unique())
        unique_times = len(arrival_times[self._temporal_column].unique())
        expected_combinations = unique_days * unique_times

        # Identify hexagons with complete temporal coverage
        coverage_counts = (
            arrival_times.groupby([self._origin_column])
            .agg({"id": "count"})
            .reset_index()
        )

        complete_hexagons = coverage_counts[
            coverage_counts["id"] == expected_combinations
        ][[self._origin_column]].copy()

        complete_hexagons = complete_hexagons.sort_values(by=[self._origin_column])
        complete_hexagons["key"] = 1  # For cross-join operations

        # Filter to only include complete hexagons
        filtered_times = arrival_times.merge(
            complete_hexagons, on=self._origin_column, how="inner"
        )

        logging.debug(
            "Filtered to %d hexagons with complete temporal coverage from %d total",
            len(complete_hexagons),
            len(coverage_counts),
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

        return filtered_times

    def _calculate_destination_probabilities(
        self, trip_data: pd.DataFrame, arrival_times: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate multinomial destination probabilities.

        Estimates conditional probability distributions P(destination | origin, time, day)
        using multinomial models for each origin-temporal-daily combination.

        Parameters
        ----------
        trip_data : DataFrame
            Raw trip data with origin-destination pairs
        arrival_times : DataFrame
            Filtered arrival times with complete coverage hexagons

        Returns
        -------
        DataFrame
            Destination probability estimates with multinomial coefficients
        """
        date_column = "date_start"

        # Get hexagons with complete coverage for creating combinations
        complete_hexagons = arrival_times[
            [self._origin_column, "key"]
        ].drop_duplicates()

        # Count actual destination trips
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

        # Create complete combination matrix for multinomial estimation
        complete_combinations = self._create_complete_combinations(
            trip_data, complete_hexagons, date_column
        )

        # Join actual counts with complete combinations
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

        # Fill missing values with zero (no trips observed)
        od_matrix["id"] = od_matrix["id"].fillna(0)

        # Calculate multinomial probabilities
        probability_estimates = self._calculate_multinomial_probabilities(od_matrix)

        logging.debug(
            "Calculated destination probabilities for %d origin-destination pairs",
            len(probability_estimates),
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

        return probability_estimates

    def _create_complete_combinations(
        self, trip_data: pd.DataFrame, complete_hexagons: pd.DataFrame, date_column: str
    ) -> pd.DataFrame:
        """
        Create all possible spatio-temporal combinations for multinomial estimation.

        Parameters
        ----------
        trip_data : DataFrame
            Raw trip data for extracting temporal patterns
        complete_hexagons : DataFrame
            Hexagons with complete temporal coverage
        date_column : str
            Name of date column for temporal grouping

        Returns
        -------
        DataFrame
            Complete combination matrix for all feasible origin-destination pairs
        """
        # Extract temporal combinations
        temporal_combinations = self._extract_temporal_combinations(
            trip_data, date_column
        )

        # Create spatial combinations (all origin-destination pairs)
        spatial_combinations = self._create_spatial_combinations(complete_hexagons)

        # Cross-join temporal and spatial combinations
        complete_combinations = temporal_combinations.merge(
            spatial_combinations, on="key"
        )
        complete_combinations = complete_combinations.drop(
            columns=["id_x", "id_y", "key"]
        )

        return complete_combinations

    def _extract_temporal_combinations(
        self, trip_data: pd.DataFrame, date_column: str
    ) -> pd.DataFrame:
        """
        Extract unique temporal combinations from trip data.

        Parameters
        ----------
        trip_data : DataFrame
            Raw trip data
        date_column : str
            Date column name

        Returns
        -------
        DataFrame
            Unique temporal combinations with cross-join key
        """
        # Get unique date-day combinations
        date_combinations = (
            trip_data.groupby([date_column, self._day_column])
            .agg({"id": "count"})
            .reset_index()
        )

        # Get unique time combinations
        time_combinations = (
            trip_data.groupby([self._temporal_column])
            .agg({"id": "count"})
            .reset_index()
        )

        # Prepare for cross-join
        date_combinations["key"] = 1
        time_combinations["key"] = 1

        # Cross-join to get all temporal combinations
        temporal_combinations = date_combinations.merge(time_combinations, on="key")

        return temporal_combinations

    def _create_spatial_combinations(
        self, complete_hexagons: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Create all origin-destination combinations from complete hexagons.

        Parameters
        ----------
        complete_hexagons : DataFrame
            Hexagons with complete temporal coverage

        Returns
        -------
        DataFrame
            All possible origin-destination pairs
        """
        origins = complete_hexagons.copy()
        destinations = complete_hexagons.copy()

        # Rename destination column for clarity
        destinations = destinations.rename(
            columns={self._origin_column: self._destination_column}
        )

        # Cross-join to create all origin-destination pairs
        spatial_combinations = origins.merge(destinations, on="key")

        return spatial_combinations

    def _calculate_multinomial_probabilities(
        self, od_matrix: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate multinomial probability coefficients for destination choice.

        For each (day, time, origin) triplet, calculates P(destination | day, time, origin)
        using observed trip frequencies.

        Parameters
        ----------
        od_matrix : DataFrame
            Origin-destination matrix with trip counts

        Returns
        -------
        DataFrame
            Multinomial probability estimates
        """
        # Aggregate daily trips by origin-destination pairs
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

        # Calculate total trips per origin for normalization
        origin_totals = (
            daily_trips.groupby(
                [self._day_column, self._temporal_column, self._origin_column]
            )
            .agg({"total_trips": "sum"})
            .reset_index()
            .rename(columns={"total_trips": "origin_total"})
        )

        # Join totals and calculate probabilities
        probability_estimates = daily_trips.merge(
            origin_totals,
            on=[self._day_column, self._temporal_column, self._origin_column],
            how="inner",
        )

        # Calculate multinomial probabilities
        probability_estimates["prob"] = (
            probability_estimates["total_trips"] / probability_estimates["origin_total"]
        )

        return probability_estimates

    def _merge_results(
        self, arrival_times: pd.DataFrame, destination_probs: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge arrival times and destination probabilities into final dataset.

        Parameters
        ----------
        arrival_times : DataFrame
            Poisson arrival rate estimates
        destination_probs : DataFrame
            Multinomial destination probability estimates

        Returns
        -------
        DataFrame
            Combined demand estimates with standardized column names
        """
        # Merge on common grouping variables
        result = destination_probs.merge(
            arrival_times,
            on=[self._day_column, self._temporal_column, self._origin_column],
            how="left",
        )

        # Standardize column names for downstream use
        result = result.rename(
            columns={"prob": "od_multinom_p_est", "id": "o_poisson_est"}
        )

        # Clean up auxiliary columns
        columns_to_drop = ["key", "origin_total", "total_trips"]
        result = result.drop(
            columns=[col for col in columns_to_drop if col in result.columns],
            errors="ignore",
        )

        logging.debug(
            "Merged results: %d rows with arrival times and destination probabilities",
            len(result),
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

        return result
