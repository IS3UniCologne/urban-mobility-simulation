"""Load a fleet's spatial supply-distribution DataFrame.

Each fleet owns a probability distribution over H3 hexagons that determines
where its vehicles spawn at the start of the simulation. The distribution comes
either from an explicit parquet file or, is derived from demand.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import h3  # type: ignore[import-untyped]
import pandas as pd

from simulation.world.demand import demand_schema

if TYPE_CHECKING:
    from pathlib import Path

    from simulation.helper.configuration.configuration import Configuration, FleetConfig


def load_fleet_supply_distribution(
    config: Configuration, fleet_config: FleetConfig
) -> pd.DataFrame:
    """Load a fleet's supply distribution.

    Parameters
    ----------
    config : Configuration
        Simulation configuration.
    fleet_config : FleetConfig
        Fleet configuration.

    Returns
    -------
    pandas.DataFrame
        Columns include ``hex_id`` and ``probability``. May
        additionally carry a ``vehicle_type`` column.
    """
    file_path = fleet_config.supply_distribution_path(config.path.PROJECT_DIR)
    demand_path = config.path.demand
    dataset_cache_dir = config.path.cache_dir
    h3_resolution = config.world.SPATIAL_RESOLUTION.value
    if file_path is not None:
        return _load_supply_distribution_parquet(file_path, h3_resolution)
    return _derive_supply_distribution_from_demand(
        demand_path, dataset_cache_dir, h3_resolution
    )


def _load_supply_distribution_parquet(path: Path, h3_resolution: int) -> pd.DataFrame:
    df = pd.read_parquet(path)
    inferred = h3.get_resolution(df["hex_id"].iloc[0])
    if inferred != h3_resolution:
        raise ValueError(
            f"Supply distribution H3 resolution {inferred} != config {h3_resolution}"
        )
    return df


def _derive_supply_distribution_from_demand(
    demand_path: Path, dataset_cache_dir: Path, h3_resolution: int
) -> pd.DataFrame:
    cache_path = _supply_distribution_cache_path(
        demand_path, dataset_cache_dir, h3_resolution
    )
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    demand_df = pd.read_parquet(demand_path)

    # Group by origin hex and sum arrival rates
    supply_df = (
        demand_df.groupby(demand_schema.ORIGIN)[demand_schema.ORIGIN_ARRIVAL_RATE]
        .sum()
        .reset_index()
        .rename(
            columns={
                demand_schema.ORIGIN: "hex_id",
                demand_schema.ORIGIN_ARRIVAL_RATE: "probability",
            }
        )
    )
    # Normalize to get a probability distribution
    supply_df["probability"] /= supply_df["probability"].sum()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    supply_df.to_parquet(cache_path, index=False)
    return supply_df


def _supply_distribution_cache_path(
    demand_path: Path, dataset_cache_dir: Path, h3_resolution: int
) -> Path:
    file_hash = hashlib.sha256(demand_path.read_bytes()).hexdigest()[:12]
    return (
        dataset_cache_dir
        / f"{file_hash}_res{h3_resolution}_supply_distribution.parquet"
    )
