"""Hex-layer derivation and on-disk caching.

The hex layer covers the bounding box with H3 cells at the configured
resolution. Building it requires only the bounding polygon and the
resolution; the result is cached as GeoParquet under the dataset's
``.cache/`` directory and re-used across runs.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import geopandas as gpd  # type: ignore[import-untyped]
import h3  # type: ignore[import-untyped]
from shapely.geometry import Polygon

from simulation.helper.cache import write_cache

if TYPE_CHECKING:
    import logging
    from pathlib import Path


def load_or_build_hex_layer(
    bbox_df: gpd.GeoDataFrame, resolution: int, cache_dir: Path, logger: logging.Logger
) -> gpd.GeoDataFrame:
    """Return the H3 hex layer for a bounding box, building and caching on first use.

    Parameters
    ----------
    bbox_df : geopandas.GeoDataFrame
        Bounding-box geometry in EPSG:4326.
    resolution : int
        H3 resolution at which to generate hex cells.
    cache_dir : Path
        Directory used to persist the derived hex layer.
    logger : logging.Logger
        Logger to emit informational/debug messages.

    Returns
    -------
    geopandas.GeoDataFrame
        Hex polygons indexed by hex ID.
    """
    cache_path = _cache_path(bbox_df, resolution, cache_dir)
    if cache_path.exists():
        logger.debug("Loading hex layer from cache: %s", cache_path)
        return gpd.read_parquet(cache_path)

    logger.info("Deriving hex layer at resolution %s from bounding box.", resolution)
    hex_df = _build_hex_layer(bbox_df, resolution)

    write_cache(hex_df, cache_path)
    return hex_df


def _cache_path(bbox_df: gpd.GeoDataFrame, resolution: int, cache_dir: Path) -> Path:
    bbox_bytes = bbox_df.union_all().wkt.encode()
    cache_key = hashlib.sha256(bbox_bytes + str(resolution).encode()).hexdigest()[:12]
    return cache_dir / f"{cache_key}_res{resolution}_hex.geoparquet"


def _build_hex_layer(bbox_df: gpd.GeoDataFrame, resolution: int) -> gpd.GeoDataFrame:
    geom = bbox_df.union_all()
    if not isinstance(geom, Polygon):
        raise TypeError(f"Bounding box must be a single Polygon, got {type(geom)}")
    exterior = list(geom.exterior.coords)
    outer = [(lat, lng) for lng, lat in exterior]  # h3 uses (lat, lng) ordering
    polygon = h3.LatLngPoly(outer)
    hex_ids = sorted(
        h3.h3shape_to_cells_experimental(polygon, res=resolution, contain="center")
    )
    hex_polys = [
        Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(hid)])
        for hid in hex_ids
    ]
    hex_df = gpd.GeoDataFrame({"geometry": hex_polys}, index=hex_ids, crs="epsg:4326")
    hex_df.index.name = "hex_id"
    return hex_df
