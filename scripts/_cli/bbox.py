"""Bounding-box GeoJSON parsing."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import h3

if TYPE_CHECKING:
    from pathlib import Path


def load_bbox_hexes(bbox_path: Path, spatial_resolution: int) -> list[str]:
    """Load a bounding-box GeoJSON and return covering H3 cells.

    Parameters
    ----------
    bbox_path : Path
        Path to a GeoJSON FeatureCollection whose first feature is a polygon.
    spatial_resolution : int
        H3 resolution at which to tessellate the polygon.

    Returns
    -------
    list of str
        Sorted H3 cell IDs covering the polygon.
    """
    with open(bbox_path) as f:
        geojson = json.load(f)
    coords = geojson["features"][0]["geometry"]["coordinates"][0]
    # GeoJSON coords are [lon, lat]; h3.LatLngPoly expects (lat, lon)
    outer = [(lat, lon) for lon, lat in coords[:-1]]
    polygon = h3.LatLngPoly(outer)
    return sorted(h3.polygon_to_cells(polygon, res=spatial_resolution))
