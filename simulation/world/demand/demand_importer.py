"""Demand data import and validation."""

from pathlib import Path

import h3  # type: ignore
import pandas as pd
from pandas import DataFrame

from simulation.helper.enums import (
    DailyResolution,
    SpatialResolution,
    TemporalResolution,
)
from simulation.helper.time import HOURS_PER_DAY
from simulation.world.demand import demand_schema


class DemandImporter:
    """Loads and validates demand files."""

    __slots__ = ("_daily_resolution", "_spatial_resolution", "_temporal_resolution")

    def __init__(
        self,
        temporal_resolution: TemporalResolution,
        spatial_resolution: SpatialResolution,
        daily_resolution: DailyResolution,
    ) -> None:
        self._temporal_resolution = temporal_resolution
        self._spatial_resolution = spatial_resolution
        self._daily_resolution = daily_resolution

    def load(self, demand_path: Path) -> DataFrame:
        """Load and validate a pre-processed demand parquet file.

        Parameters
        ----------
        demand_path : Path
            Path to demand.parquet.

        Returns
        -------
        DataFrame
            Validated demand data.

        Raises
        ------
        ValueError
            If demand data does not match expected values based on config.
        """
        df = pd.read_parquet(demand_path)
        self._validate(df)
        return df

    def _validate(self, df: DataFrame) -> None:
        inferred_h3_res = h3.get_resolution(df[demand_schema.ORIGIN].iloc[0])
        if inferred_h3_res != self._spatial_resolution.value:
            raise ValueError(
                f"Demand H3 resolution {inferred_h3_res} != config {self._spatial_resolution.value}"
            )

        inferred_bucket_hours = HOURS_PER_DAY // df[demand_schema.TIME_BUCKET].nunique()
        if inferred_bucket_hours != self._temporal_resolution.value:
            raise ValueError(
                f"Demand temporal bucket {inferred_bucket_hours}h != config {self._temporal_resolution.value}h"
            )

        if self._daily_resolution == DailyResolution.WEEKDAY_WEEKEND:
            # TODO: this whole config value can probably be deprecated?
            if df[demand_schema.IS_WEEKEND].nunique() < 2:
                raise ValueError(
                    "Config requires weekday/weekend split but demand data has only one day type"
                )
