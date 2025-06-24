"""DemandCacheManager handles caching of processed demand data."""

import logging
from pathlib import Path

import pandas as pd


class DemandCacheManager:
    """Handles caching of processed demand data."""

    def __init__(self, city: str) -> None:
        self._city = city

    def get_cache_path(self, temporal_column: str, origin_column: str) -> Path:
        """Generate cache file path for given parameters.

        Parameters
        ----------
        temporal_column : str
            Name of the temporal column (e.g., 'time_bucket_4h')
        origin_column : str
            Name of the origin column (e.g., 'h3_start_7')

        Returns
        -------
        Path
            Path to the cache file for the given city, temporal column, and origin column.
        """
        return Path(
            "data/demand/",
            f"{self._city}_weekday_{temporal_column}_{origin_column}.parquet",
        )

    def load_cached_data(self, cache_path: Path) -> pd.DataFrame | None:
        """
        Load data from cache if it exists.

        Parameters
        ----------
        cache_path : Path
            Path to the cache file.

        Returns
        -------
        pd.DataFrame or None
            DataFrame containing the cached data, or None if no cache exists.
        """
        file_path = cache_path.with_suffix(".parquet")
        if file_path.exists():
            logging.debug(
                "Loading demand data from cache: %s",
                file_path,
                extra={"clazz": self.__class__.__name__},
            )
            return pd.read_parquet(file_path)
        return None

    def save_to_cache(self, data: pd.DataFrame, cache_path: Path) -> None:
        """Save processed data to cache.

        Parameters
        ----------
        data : pd.DataFrame
            DataFrame containing the processed demand data to be cached.
        cache_path : Path
            Path to the cache file where the data should be saved.
        """
        data.to_parquet(cache_path, index=False)
