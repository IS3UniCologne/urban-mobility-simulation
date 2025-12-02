"""User log entries represent single successful or failed trip requests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from simulation.helper.configuration.enums import TransactionState, VehicleType

if TYPE_CHECKING:
    from simulation.helper.types import RegionId, SimId


@dataclass(frozen=True, slots=True)
class BaseUserLogEntry:
    """
    Base class for all user log entries.

    Attributes
    ----------
    user_uid : SimId
        ID of the user who made the request.
    origin : RegionId
        Origin region ID.
    destination : RegionId
        Destination region ID.
    outcome_state : TransactionState
        Final outcome (FULFILLED or MISSED).
    search_start_time : float
        Simulation time when the user started searching.
    search_end_time : float
        Simulation time when the user finished searching.
    outcome_time : float
        Simulation time when the outcome was determined.
    attempted_operator_uids : list[SimId]
        List of operator UIDs that were attempted.
    """

    user_uid: SimId
    origin: RegionId
    destination: RegionId
    outcome_state: TransactionState
    search_start_time: float
    search_end_time: float
    outcome_time: float
    attempted_operator_uids: list[SimId]

    @property
    def search_duration(self) -> float:
        """Total time spent searching for transportation."""
        return self.search_end_time - self.search_start_time

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary including computed properties."""
        data = asdict(self)
        data["search_duration"] = self.search_duration
        if self.outcome_state:
            data["outcome_state"] = self.outcome_state.value
        return data


@dataclass(frozen=True, slots=True)
class FulfilledUserLogEntry(BaseUserLogEntry):
    """
    User log entry for a fulfilled trip.

    Attributes
    ----------
    fulfilled_by_operator_uid : SimId
        ID of the operator that fulfilled the trip.
    vehicle_uid : SimId
        UID of the vehicle that served the trip.
    vehicle_type : VehicleType
        Type of vehicle used.
    actual_wait_time : float
        Actual waiting time experienced by the user.
    trip_start_time : float
        Simulation time when the trip started.
    trip_end_time : float
        Simulation time when the trip ended.
    energy_consumed : float
        Energy consumed during the trip.
    price_paid : float
        Price paid by the user.
    """

    fulfilled_by_operator_uid: SimId
    vehicle_uid: SimId
    vehicle_type: VehicleType
    actual_wait_time: float
    trip_start_time: float
    trip_end_time: float
    energy_consumed: float
    price_paid: float

    @property
    def trip_duration(self) -> float:
        """Calculate trip duration."""
        return self.trip_end_time - self.trip_start_time

    def __post_init__(self) -> None:
        """Validate that state is FULFILLED."""
        if self.outcome_state != TransactionState.FULFILLED:
            msg = f"FulfilledUserLogEntry must have state FULFILLED, got {self.outcome_state}"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary including computed properties and enum values."""
        data = super(
            FulfilledUserLogEntry, self
        ).to_dict()  # super() does not work with frozen dataclasses
        data["trip_duration"] = self.trip_duration
        if self.vehicle_type:
            data["vehicle_type"] = self.vehicle_type.value
        return data


@dataclass(frozen=True, slots=True)
class MissedUserLogEntry(BaseUserLogEntry):
    """User log entry for a missed or withdrawn trip."""

    def __post_init__(self) -> None:
        """Validate that state is MISSED or WITHDRAWN."""
        if self.outcome_state not in (
            TransactionState.MISSED,
            TransactionState.WITHDRAWN,
        ):
            msg = f"MissedUserLogEntry must have state MISSED or WITHDRAWN, got {self.outcome_state}"
            raise ValueError(msg)


# Type alias for any user log entry
UserLogEntry = FulfilledUserLogEntry | MissedUserLogEntry
