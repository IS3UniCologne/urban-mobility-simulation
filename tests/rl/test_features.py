"""Tests for the observation helpers in rl.problems.features."""

from __future__ import annotations

import pytest

pytest.importorskip("gymnasium")

from rl.problems.features import state_shares
from simulation.helper.vehicle_states import VehicleStates
from tests.rl.fakes import FakeVehicle


def test_state_shares_rejects_an_empty_fleet() -> None:
    with pytest.raises(ValueError, match="at least one vehicle"):
        state_shares([])


def test_state_shares_rejects_a_state_outside_the_groups() -> None:
    vehicles = [FakeVehicle("v1", state=VehicleStates.SERVICING)]
    with pytest.raises(ValueError, match="SERVICING"):
        state_shares(vehicles)
