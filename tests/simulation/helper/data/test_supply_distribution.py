"""Tests for the supply-distribution loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

import h3
import pandas as pd
import pytest

from simulation.helper.data.supply_distribution import _load_supply_distribution_parquet
from simulation.helper.enums import VehicleType

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

_RESOLUTION = 7
_HEXES = sorted(
    {
        h3.latlng_to_cell(52.50, 13.40, _RESOLUTION),
        h3.latlng_to_cell(52.52, 13.42, _RESOLUTION),
        h3.latlng_to_cell(52.48, 13.38, _RESOLUTION),
    }
)


def _write_supply(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "supply.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def test_unnormalized_columns_are_normalized_to_one(tmp_path: Path) -> None:
    # Probabilities deliberately do not sum to 1 (0.2 + 0.2 = 0.4).
    rows = [
        {"hex_id": _HEXES[0], "vehicle_type": "Car", "probability": 0.2},
        {"hex_id": _HEXES[1], "vehicle_type": "Car", "probability": 0.2},
    ]
    wide = _load_supply_distribution_parquet(_write_supply(tmp_path, rows), _RESOLUTION)

    assert list(wide.columns) == [VehicleType.CAR]
    assert wide[VehicleType.CAR].sum() == pytest.approx(1.0)
    assert wide.loc[_HEXES[0], VehicleType.CAR] == pytest.approx(0.5)


def test_columns_are_vehicle_type_enums(tmp_path: Path) -> None:
    rows = [
        {"hex_id": _HEXES[0], "vehicle_type": "Car", "probability": 1.0},
        {"hex_id": _HEXES[1], "vehicle_type": "Scooter", "probability": 1.0},
    ]
    wide = _load_supply_distribution_parquet(_write_supply(tmp_path, rows), _RESOLUTION)

    assert set(wide.columns) == {VehicleType.CAR, VehicleType.SCOOTER}
    # Missing hexes for a present type are filled with 0.0, each column sums to 1.
    assert wide[VehicleType.CAR].sum() == pytest.approx(1.0)
    assert wide[VehicleType.SCOOTER].sum() == pytest.approx(1.0)


def test_unknown_vehicle_type_raises(tmp_path: Path) -> None:
    rows = [{"hex_id": _HEXES[0], "vehicle_type": "car", "probability": 1.0}]
    with pytest.raises(ValueError, match="Unknown vehicle type 'car'"):
        _load_supply_distribution_parquet(_write_supply(tmp_path, rows), _RESOLUTION)


def test_zero_probability_type_raises(tmp_path: Path) -> None:
    rows = [{"hex_id": _HEXES[0], "vehicle_type": "Car", "probability": 0.0}]
    with pytest.raises(ValueError, match="zero total probability"):
        _load_supply_distribution_parquet(_write_supply(tmp_path, rows), _RESOLUTION)


def test_resolution_mismatch_raises(tmp_path: Path) -> None:
    rows = [{"hex_id": _HEXES[0], "vehicle_type": "Car", "probability": 1.0}]
    with pytest.raises(ValueError, match="resolution"):
        _load_supply_distribution_parquet(
            _write_supply(tmp_path, rows), _RESOLUTION + 1
        )
