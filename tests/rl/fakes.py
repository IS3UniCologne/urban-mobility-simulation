"""Fakes for the operator internals the problems and the Bookkeeper read."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from simulation.agent.user.user_log.user_log_entry import (
    FulfilledUserLogEntry,
    MissedUserLogEntry,
)
from simulation.helper.enums import TransactionState, VehicleType
from simulation.helper.types import SimId
from simulation.helper.vehicle_states import VehicleState, VehicleStates
from simulation.metrics.statistics.user_log_stats import UserLogStats
from simulation.operator.accounting import CostType
from simulation.operator.operator_log.operator_log_entry import (
    FulfilledOperatorLogEntry,
    MissedOperatorLogEntry,
)

if TYPE_CHECKING:
    from simulation.agent.user.user_log.user_log_entry import UserLogEntry
    from simulation.helper.types import RegionId

OPERATOR_ID = SimId("Operator_1")


@dataclass(eq=False)
class FakeVehicle:
    """Fake vehicle with the attributes the problems read."""

    uid: str
    state: VehicleState = VehicleStates.STANDBY
    cost_per_km: float = 0.0
    metres_per_min: float = 100.0

    @property
    def cost_config(self) -> SimpleNamespace:
        """Cost rates reporting ``cost_per_km`` as the distance rate."""
        return SimpleNamespace(PER_KM=self.cost_per_km)

    def calculate_travel_time(self, distance: float) -> float:
        """Return the minutes ``distance`` metres take at ``metres_per_min``."""
        return distance / self.metres_per_min


@dataclass
class FakeFleet:
    """Fake fleet holding a static vehicle list."""

    vehicles: list[FakeVehicle]


class FakeLedger:
    """Fake ledger with settable revenue and per-type cost totals."""

    def __init__(self) -> None:
        self.revenue_total = 0.0
        self.costs: dict[CostType, float] = dict.fromkeys(CostType, 0.0)

    def revenue(self) -> float:
        """Return the running revenue total."""
        return self.revenue_total

    def costs_by_type(self) -> dict[CostType, float]:
        """Return a copy of the running cost totals."""
        return dict(self.costs)


class FakeOperatorLog:
    """Fake operator log with a plain transaction list."""

    def __init__(self) -> None:
        self.transactions: list[Any] = []


class FakeUserLog:
    """Fake user log whose statistics are the real ``UserLogStats``, fed through ``log_trip_outcome``."""

    def __init__(self) -> None:
        self.metrics = UserLogStats()

    def log_trip_outcome(self, outcome: UserLogEntry) -> None:
        """Feed an outcome to the statistics."""
        self.metrics.on_outcome(outcome)


def make_fulfilled(origin: RegionId, price: float = 10.0) -> FulfilledOperatorLogEntry:
    """Build a fulfilled log entry with the given origin."""
    return FulfilledOperatorLogEntry(
        origin=origin,
        destination=origin,
        time_start=0.0,
        time_end=1.0,
        distance=100.0,
        accepted_vehicle_types=frozenset({VehicleType.CAR}),
        state=TransactionState.FULFILLED,
        price=price,
        vehicle_uid="Vehicle_1",
        selected_vehicle_type=VehicleType.CAR,
        est_pickup_wait=1.0,
        energy_consumption=1.0,
        selected_vehicle_EV=True,
        duration=1.0,
    )


def make_missed(origin: RegionId) -> MissedOperatorLogEntry:
    """Build a missed log entry with the given origin."""
    return MissedOperatorLogEntry(
        origin=origin,
        destination=origin,
        time_start=0.0,
        time_end=1.0,
        distance=100.0,
        accepted_vehicle_types=frozenset({VehicleType.CAR}),
        state=TransactionState.MISSED,
        price=10.0,
    )


def make_served(wait_min: float) -> FulfilledUserLogEntry:
    """Build a user log entry of a served user who waited ``wait_min``."""
    return FulfilledUserLogEntry(
        user_uid=SimId("User_1"),
        origin="a",
        destination="b",
        outcome_state=TransactionState.FULFILLED,
        search_start_time=0.0,
        search_end_time=1.0,
        outcome_time=10.0,
        attempted_operator_uids=[OPERATOR_ID],
        fulfilled_by_operator_uid=OPERATOR_ID,
        vehicle_uid=SimId("Vehicle_1"),
        vehicle_type=VehicleType.CAR,
        actual_wait_time=wait_min,
        trip_start_time=1.0 + wait_min,
        trip_end_time=10.0,
        energy_consumed=1.0,
        price_paid=10.0,
    )


def make_lost() -> MissedUserLogEntry:
    """Build a user log entry of a user whose search ran out."""
    return MissedUserLogEntry(
        user_uid=SimId("User_2"),
        origin="a",
        destination="b",
        outcome_state=TransactionState.MISSED,
        search_start_time=0.0,
        search_end_time=10.0,
        outcome_time=10.0,
        attempted_operator_uids=[],
    )


def make_operator(vehicles: list[FakeVehicle]) -> SimpleNamespace:
    """Assemble a fake operator around the other fakes."""
    return SimpleNamespace(
        uid=OPERATOR_ID,
        fleet=FakeFleet(vehicles),
        operations=SimpleNamespace(),
        operator_log=FakeOperatorLog(),
        ledger=FakeLedger(),
    )


def make_simulation(vehicles: list[FakeVehicle], now: float = 0.0) -> SimpleNamespace:
    """Assemble a fake simulation around a world with one fake operator."""
    return SimpleNamespace(
        sim=SimpleNamespace(time=now),
        world=SimpleNamespace(
            operators=[make_operator(vehicles)], user_log=FakeUserLog()
        ),
    )


def operator_of(simulation: SimpleNamespace) -> SimpleNamespace:
    """Return the fake operator of a fake simulation."""
    return simulation.world.operators[0]
