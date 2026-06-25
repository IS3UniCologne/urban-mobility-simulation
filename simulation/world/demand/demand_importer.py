"""Demand data import and processing.

This module provides the DemandImporter class which coordinates the import
and processing and caching of transportation demand data,
"""

from pathlib import Path

import pandas as pd
from pandas import DataFrame

from simulation.helper.enums import (
    DailyResolution,
    SpatialResolution,
    TemporalResolution,
)

from .demand_cache_manager import DemandCacheManager
from .demand_processor import DemandProcessor


class DemandImporter:
    """Coordinates demand data import and processing."""

    __slots__ = (
        "_cache_manager",
        "_city",
        "_daily_resolution",
        "_spatial_resolution",
        "_temporal_resolution",
    )

    def __init__(
        self,
        temporal_resolution: TemporalResolution,
        spatial_resolution: SpatialResolution,
        daily_resolution: DailyResolution,
        city: str,
    ) -> None:
        self._temporal_resolution: TemporalResolution = temporal_resolution
        self._spatial_resolution: SpatialResolution = spatial_resolution
        self._daily_resolution: DailyResolution = daily_resolution
        self._city = city

        self._cache_manager = DemandCacheManager(city)

    def extract_spatio_temporal_demand_estimates(
        self, trip_data_path: Path
    ) -> pd.DataFrame:
        """Extract demand estimates from trip data.

        Returns a DataFrame with distributional data regarding arrival times (poisson) and origin destination trips (frequency)
        in spatio-temporal resolution.

        Parameters
        ----------
        trip_data_path : Path
            Path to the trip data file

        Returns
        -------
        DataFrame
            Contains the following columns:
                - is_holiday: yes/no (!weekday)
                - temporal bucket: TemporalResolution
                - origin: Hexagon ID by given resolution
                - destination: Hexagon ID by given resolution
                - od_multinom_p_est: Multionomial Distribution Coeffcients for P(D | is_holiday, temp_bucket, origin). Add up to 1 for each triplet.
                - o_poisson_est: Lambda of poisson distribution for each triplet (is_holiday, temp_bucket, origin); destination not considered

        Raises
        ------
        NotImplementedError
        If the daily resolution is not supported.
        """
        if self._daily_resolution != DailyResolution.WEEKDAY_WEEKEND:
            raise NotImplementedError(
                "Currently only weekday/weekend distinction supported."
            )

        # Try to load from cache first
        cache_path: Path = self._cache_manager.get_cache_path(
            temporal_column=self._temporal_resolution.column_name,
            origin_column=self._spatial_resolution.origin_column_name,
        )
        cached_data: DataFrame | None = self._cache_manager.load_cached_data(cache_path)
        if cached_data is not None:
            return cached_data

        # Process data if not cached
        processor: DemandProcessor = DemandProcessor(
            spatial_columns=self._spatial_resolution.origin_destination_columns,
            temporal_column=self._temporal_resolution.column_name,
            day_column=self._daily_resolution.day_of_week_column_name,
        )
        result: DataFrame = processor.process_trip_data(trip_data_path=trip_data_path)

        # Cache the result
        self._cache_manager.save_to_cache(data=result, cache_path=cache_path)

        return result
