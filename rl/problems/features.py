"""Helpers that build the entries of the observation space."""

from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np
from gymnasium.spaces import Box

from simulation.helper.time import MINUTES_PER_DAY
from simulation.helper.vehicle_states import VehicleStates

if TYPE_CHECKING:
    from collections.abc import Sequence

    from simulation.helper.vehicle_states import VehicleState
    from simulation.vehicle.vehicle import Vehicle

STATE_GROUPS = (
    VehicleStates.STANDBY,
    VehicleStates.TRANSPORTING,
    VehicleStates.RELOCATING,
    VehicleStates.WAITING_FOR_CHARGING,
    VehicleStates.CHARGING,
    VehicleStates.OFFLINE,
)
"""Vehicle states that ``state_shares`` reports, one share each.

Vehicle states form a tree.
A vehicle on a trip is in one of the children of ``TRANSPORTING`` (``PICK_UP``, ``DRIVING``, ``WAITING_FOR_USER`` and so on) and counts toward ``TRANSPORTING``.
The other five groups are the states a vehicle is set to directly.
``SERVICING`` is only the parent of ``RELOCATING``, ``CHARGING`` and ``WAITING_FOR_CHARGING`` and is never set itself.
"""

STATE_FEATURES = tuple(state.name.lower() for state in STATE_GROUPS)
"""Entry names of the shares in ``STATE_GROUPS``, in the same order: ``standby`` to ``offline``."""

CLOCK_FEATURES = ("clock_sin", "clock_cos")
"""Entry names of the sine and cosine of the time of day, both in -1 to 1."""


def box(features: Sequence[str], signed_entries: Sequence[str] = ()) -> Box[np.float32]:
    """Return the observation space for the ``features``.

    Follows the Gymnasium convention of ``low`` and ``high`` arrays, with ``dtype`` float32.

    Parameters
    ----------
    features : sequence of str
        Entry names in observation order.
    signed_entries : sequence of str
        Names of the entries that can go negative, such as ``CLOCK_FEATURES``.

    Returns
    -------
    Box
        Observation space with the entries of ``features`` in the same order.
    """
    low = [-1.0 if name in signed_entries else 0.0 for name in features]
    return Box(
        low=np.array(low, dtype=np.float32),
        high=np.ones(len(features), dtype=np.float32),
        dtype=np.float32,
    )


def state_shares(vehicles: Sequence[Vehicle]) -> dict[str, float]:
    """Return the share of ``vehicles`` in each state of ``STATE_GROUPS``, keyed by ``STATE_FEATURES`` and summing to one.

    Raises
    ------
    ValueError
        If ``vehicles`` is empty or a vehicle is in a state outside ``STATE_GROUPS``.
    """
    if not vehicles:
        msg = "state_shares needs at least one vehicle, got none."
        raise ValueError(msg)
    counts = Counter(_state_group(vehicle.state) for vehicle in vehicles)
    return {
        name: counts[group] / len(vehicles)
        for name, group in zip(STATE_FEATURES, STATE_GROUPS, strict=True)
    }


def _state_group(state: VehicleState) -> VehicleState:
    """Return the state of ``STATE_GROUPS`` that ``state`` counts toward, ``TRANSPORTING`` for every trip state."""
    if state.is_descendant_of(VehicleStates.TRANSPORTING):
        return VehicleStates.TRANSPORTING
    if state not in STATE_GROUPS:
        msg = f"Vehicle state {state.name} is not in STATE_GROUPS, so state_shares cannot count it."
        raise ValueError(msg)
    return state


def clock(time_min: float) -> dict[str, float]:
    """Return the sine and cosine of the time of day at the simulation time ``time_min`` (min), keyed by ``CLOCK_FEATURES``.

    The pair puts 23:59 and 00:00 close together, which the minute of the day alone does not.
    """
    angle = 2 * math.pi * (time_min % MINUTES_PER_DAY) / MINUTES_PER_DAY
    return dict(zip(CLOCK_FEATURES, (math.sin(angle), math.cos(angle)), strict=True))


def squash(value: float, scale: float) -> float:
    """Return ``value`` mapped into 0 to 1 as value / (scale + value), for entries with no upper bound.

    Small values keep their resolution and large values approach 1.

    Parameters
    ----------
    value : float
        Value to map, 0 or more.
    scale : float
        Value that maps to 0.5.
    """
    return value / (scale + value)


def unsquash(entry: float) -> float:
    """Return the value behind a ``squash`` entry divided by its scale, infinity for an entry of 1."""
    return entry / (1.0 - entry) if entry < 1.0 else math.inf
