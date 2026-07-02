"""Load a fleet's spatial supply-distribution."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import h3  # type: ignore[import-untyped]
import pandas as pd

from simulation.helper.enums import VehicleType
from simulation.world.demand import demand_schema

if TYPE_CHECKING:
    from pathlib import Path

    from simulation.helper.configuration.configuration import Configuration, FleetConfig


def load_fleet_supply_distribution(
    config: Configuration, fleet_config: FleetConfig
) -> pd.DataFrame:
    """Load a fleet's supply distribution.

    Source resolution order:
    1: fleet-level ``SUPPLY_DISTRIBUTION_FILE``
    2: dataset-level ``supply.parquet``
    3: derive from demand arrival rates

    Parameters
    ----------
    config : Configuration
        Simulation configuration.
    fleet_config : FleetConfig
        Fleet configuration.

    Returns
    -------
    pandas.DataFrame
        Wide frame indexed by sorted ``hex_id``, one column per
        ``VehicleType`` present in the source; each column sums to 1.0,
        with missing hexes filled with 0.0::

            hex_id            CAR  SCOOTER
            8a1fb46622dffff   0.6      0.3
            8a1fb46627bffff   0.4      0.7
    """
    file_path = fleet_config.supply_distribution_path(config.path.PROJECT_DIR)
    if file_path is None:
        file_path = config.path.supply
    h3_resolution = config.world.SPATIAL_RESOLUTION.value
    fleet_vehicle_types = [vc.VEHICLE_TYPE for vc in fleet_config.VEHICLES]

    if file_path is not None:
        return _load_supply_distribution_parquet(file_path, h3_resolution)
    return _derive_supply_distribution_from_demand(
        config.path.demand, config.path.cache_dir, h3_resolution, fleet_vehicle_types
    )


def _load_supply_distribution_parquet(path: Path, h3_resolution: int) -> pd.DataFrame:
    df = pd.read_parquet(path)
    inferred = h3.get_resolution(df["hex_id"].iloc[0])
    if inferred != h3_resolution:
        raise ValueError(
            f"Supply distribution H3 resolution {inferred} != config {h3_resolution}"
        )
    df = df.assign(vehicle_type=df["vehicle_type"].map(VehicleType))
    wide = (
        df.pivot(index="hex_id", columns="vehicle_type", values="probability")
        .fillna(0.0)
        .sort_index()
    )
    return _normalize_columns(wide, path)


def _normalize_columns(wide: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Normalize each per-type column to a probability distribution summing to 1."""
    totals = wide.sum(axis=0)
    zero_types = totals[totals == 0.0].index.tolist()
    if zero_types:
        raise ValueError(
            f"Supply distribution {path.name} has zero total probability for "
            f"vehicle type(s): {[str(t) for t in zero_types]}."
        )
    return wide / totals


def _derive_supply_distribution_from_demand(
    demand_path: Path,
    dataset_cache_dir: Path,
    h3_resolution: int,
    fleet_vehicle_types: list[VehicleType],
) -> pd.DataFrame:
    """Derive a supply distribution from demand arrival rates, normalized to a probability distribution."""
    cache_path = _supply_distribution_cache_path(
        demand_path, dataset_cache_dir, h3_resolution
    )
    if cache_path.exists():
        probs = pd.read_parquet(cache_path).set_index("hex_id")["probability"]
    else:
        demand_df = pd.read_parquet(demand_path)
        cells = demand_df.drop_duplicates(
            [demand_schema.ORIGIN, demand_schema.TIME_BUCKET, demand_schema.IS_WEEKEND]
        )
        probs = (
            cells.groupby(demand_schema.ORIGIN)[demand_schema.ORIGIN_ARRIVAL_RATE]
            .sum()
            .rename_axis("hex_id")
            .rename("probability")
        )
        probs = probs / probs.sum()

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        probs.reset_index().to_parquet(cache_path, index=False)

    probs = probs.sort_index()
    # Assign same distribution to all vehicle types
    return pd.DataFrame({vt: probs for vt in fleet_vehicle_types})


def _supply_distribution_cache_path(
    demand_path: Path, dataset_cache_dir: Path, h3_resolution: int
) -> Path:
    file_hash = hashlib.sha256(demand_path.read_bytes()).hexdigest()[:12]
    return (
        dataset_cache_dir
        / f"{file_hash}_res{h3_resolution}_supply_distribution.parquet"
    )
