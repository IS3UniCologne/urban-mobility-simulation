"""Bounding-box loading, inference, and hex-coverage validation.

If no bounding box file is provided, it is inferred from the supply and demand files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import geopandas as gpd  # type: ignore[import-untyped]
import h3  # type: ignore[import-untyped]
import pandas as pd
from shapely.geometry import MultiPoint

from simulation.world.demand import demand_schema

if TYPE_CHECKING:
    import logging
    from pathlib import Path


def read_demand_hex_ids(demand_path: Path) -> set[str]:
    """Return the union of origin and destination hex IDs in a demand parquet."""
    df = pd.read_parquet(
        demand_path, columns=[demand_schema.ORIGIN, demand_schema.DESTINATION]
    )
    # set() walks an Arrow-backed column row by row in Python, so deduplicate first
    return set(df[demand_schema.ORIGIN].unique()) | set(
        df[demand_schema.DESTINATION].unique()
    )


def read_supply_hex_ids(supply_paths: list[Path]) -> dict[Path, set[str]]:
    """Return the hex IDs contributed by each supply parquet, keyed by path."""
    return {
        path: set(pd.read_parquet(path, columns=["hex_id"])["hex_id"])
        for path in supply_paths
    }


def load_or_infer_bounding_box(
    bbox_path: Path | None,
    demand_hex_ids: set[str],
    supply_hex_ids_by_path: dict[Path, set[str]],
    logger: logging.Logger,
) -> gpd.GeoDataFrame:
    """Load a bounding box from file or infer it from demand+supply hex IDs.

    Parameters
    ----------
    bbox_path : Path or None
        Optional path to ``bounding_box.geojson``. When ``None``, the bounding
        polygon is inferred from the convex hull of all demand and supply
        hex centroids.
    demand_hex_ids : set of str
        Origin and destination hex IDs from the demand parquet.
    supply_hex_ids_by_path : dict of (Path, set of str)
        Hex IDs from each supply parquet that contributes to the simulation.
    logger : logging.Logger
        Logger to emit informational and warning messages.

    Returns
    -------
    geopandas.GeoDataFrame
        Bounding-box geometry in EPSG:4326.
    """
    if bbox_path is not None:
        bbox_df = gpd.read_file(bbox_path)
        if bbox_df.crs is None:
            logger.warning("Bounding box CRS is None. Defaulting to EPSG:4326.")
            bbox_df.set_crs("epsg:4326", inplace=True)
        return bbox_df

    logger.info("No bounding_box.geojson found. Inferring from demand + supply data.")
    hex_ids = set(demand_hex_ids)
    for supply_hexes in supply_hex_ids_by_path.values():
        hex_ids |= supply_hexes
    latlngs = [h3.cell_to_latlng(hid) for hid in hex_ids]
    hull = MultiPoint([(lng, lat) for lat, lng in latlngs]).convex_hull
    return gpd.GeoDataFrame({"geometry": [hull]}, crs="epsg:4326")


def warn_hex_mismatches(
    hex_df: gpd.GeoDataFrame,
    demand_hex_ids: set[str],
    supply_hex_ids_by_path: dict[Path, set[str]],
    logger: logging.Logger,
) -> None:
    """Warn if demand or supply data references hex IDs outside the hex grid.

    Hex IDs outside the grid yield unreachable origins/destinations or supply
    locations and might indicate a bounding box mismatch.
    """
    hex_set = set(hex_df.index)
    outside = demand_hex_ids - hex_set
    if outside:
        logger.warning(
            "%d demand hex ID(s) fall outside the hex grid (e.g. %s). "
            "These origins/destinations will be unreachable.",
            len(outside),
            next(iter(outside)),
        )
    for supply_path, supply_hexes in supply_hex_ids_by_path.items():
        outside_supply = supply_hexes - hex_set
        if outside_supply:
            logger.warning(
                "%d supply hex ID(s) in %s fall outside the hex grid (e.g. %s).",
                len(outside_supply),
                supply_path.name,
                next(iter(outside_supply)),
            )
