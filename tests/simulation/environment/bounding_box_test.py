"""Tests for the grid inferred from demand and supply hexagons."""

import logging
from pathlib import Path

import h3
import pytest

from simulation.environment.bounding_box import load_or_infer_bounding_box
from simulation.environment.hex_layer import load_or_build_hex_layer

pytestmark = pytest.mark.unit


def test_inferred_grid_keeps_every_input_hexagon(tmp_path: Path) -> None:
    # in a ring every hexagon centre is on the edge of a hull through the centres
    hex_ids = set(h3.grid_ring(h3.latlng_to_cell(52.52, 13.40, 7), 2))
    logger = logging.getLogger(__name__)

    bbox = load_or_infer_bounding_box(None, hex_ids, {}, logger)
    grid = load_or_build_hex_layer(bbox, 7, tmp_path, logger)

    assert hex_ids <= set(grid.index)
