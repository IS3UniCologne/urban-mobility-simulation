"""Operator log entries represent single successful or failed transactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.helper.enums import TransactionState, VehicleType

if TYPE_CHECKING:
    from simulation.helper.types import RegionId, SimId


@dataclass(frozen=True, slots=True)
class BaseOperatorLogEntry:
    """
    Base class for all operator log entries.

    Attributes
    ----------
    origin : RegionId
        Region ID of the trip origin.
    destination : RegionId
        Region ID of the trip destination.
    time_start : float
        Simulation time when the trip started.
    time_end : float
        Simulation time when the trip ended.
    distance : float
        Distance traveled during the trip.
    accepted_vehicle_types : frozenset of VehicleType
        Set of accepted vehicle types for the trip.
    state : TransactionState
        State of the transaction.
    price : float
        Price paid for the trip.
    """

    origin: RegionId
    destination: RegionId
    time_start: float
    time_end: float
    distance: float
    accepted_vehicle_types: frozenset[VehicleType]
    state: TransactionState
    price: float


@dataclass(frozen=True, slots=True)
class FulfilledOperatorLogEntry(BaseOperatorLogEntry):
    """
    Operator log entry for a fulfilled transaction.

    Contains additional data specific to fulfilled trips.

    Attributes
    ----------
    vehicle_uid : SimId
        Unique identifier for the vehicle.
    selected_vehicle_type : VehicleType
        Selected vehicle type for the trip.
    est_pickup_wait : float
        Estimated wait time from request creation until pickup.
    energy_consumption : float
        Energy consumed during the trip.
    selected_vehicle_EV : bool
        Whether the selected vehicle is electric.
    revenue : float
        Revenue earned from the trip for the operator.
    duration : float
        Duration of the trip.
    """

    vehicle_uid: SimId
    selected_vehicle_type: VehicleType
    est_pickup_wait: float
    energy_consumption: float
    selected_vehicle_EV: bool
    revenue: float
    duration: float

    def __post_init__(self) -> None:
        """Validate that state is FULFILLED."""
        if self.state != TransactionState.FULFILLED:
            msg = (
                f"FulfilledOperatorLogEntry must have state FULFILLED, got {self.state}"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MissedOperatorLogEntry(BaseOperatorLogEntry):
    """Operator log entry for a missed or withdrawn transaction."""

    def __post_init__(self) -> None:
        """Validate that state is MISSED or WITHDRAWN."""
        if self.state not in (TransactionState.MISSED, TransactionState.WITHDRAWN):
            msg = f"MissedOperatorLogEntry must have state MISSED or WITHDRAWN, got {self.state}"
            raise ValueError(msg)


# Type alias for any operator log entry
OperatorLogEntry = FulfilledOperatorLogEntry | MissedOperatorLogEntry
