"""Incremental stats tracker for OperatorLog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.enums import TransactionState
from simulation.operator.operator_log.operator_log_entry import (
    FulfilledOperatorLogEntry,
    MissedOperatorLogEntry,
)

if TYPE_CHECKING:
    from simulation.operator.operator_log.operator_log_entry import OperatorLogEntry


class OperatorLogStats:
    """
    Stats tracker for OperatorLog.

    Incrementally updates with every new transaction to provide O(1) access to common statistics.

    Attributes
    ----------
    fulfilled_count : int
        Number of fulfilled transactions.
    has_fulfilled : bool
        Whether any transaction has been fulfilled.
    missed_count : int
        Number of missed transactions.
    total_count : int
        Total number of transactions.
    total_distance : float
        Total distance of all fulfilled transactions.
    total_duration : float
        Total duration of all fulfilled transactions.
    total_energy : float
        Total energy consumption of all fulfilled transactions.
    total_missed_revenue : float
        Total revenue lost from missed transactions.
    total_price_sum : float
        Sum of prices of all fulfilled transactions.
    withdrawn_count : int
        Number of withdrawn transactions.
    """

    __slots__ = (
        "fulfilled_count",
        "has_fulfilled",
        "missed_count",
        "total_count",
        "total_distance",
        "total_duration",
        "total_energy",
        "total_missed_revenue",
        "total_price_sum",
        "withdrawn_count",
    )

    def __init__(self) -> None:
        self.total_count = 0
        self.fulfilled_count = 0
        self.missed_count = 0
        self.withdrawn_count = 0
        self.total_missed_revenue = 0.0
        self.total_duration = 0.0
        self.total_distance = 0.0
        self.total_energy = 0.0
        self.total_price_sum = 0.0
        self.has_fulfilled = False

    def on_transaction(self, transaction: OperatorLogEntry) -> None:
        """
        Update metrics when a transaction is added.

        Parameters
        ----------
        transaction : OperatorLogEntry
            The transaction to use for updating the incremental metrics.
        """
        self.total_count += 1

        if isinstance(transaction, FulfilledOperatorLogEntry):
            self.fulfilled_count += 1
            self.has_fulfilled = True
            self.total_price_sum += transaction.price
            self.total_duration += transaction.duration
            self.total_distance += transaction.distance
            if transaction.energy_consumption is not None:
                self.total_energy += transaction.energy_consumption
        elif isinstance(transaction, MissedOperatorLogEntry):
            if transaction.state == TransactionState.MISSED:
                self.missed_count += 1
                self.total_missed_revenue += transaction.price

            elif transaction.state == TransactionState.WITHDRAWN:
                self.withdrawn_count += 1

    @property
    def total_fulfilled_trips(self) -> int:
        """Get the total number of fulfilled trips."""
        return self.fulfilled_count

    @property
    def total_missed_trips(self) -> int:
        """Get the total number of missed trips."""
        return self.missed_count + self.withdrawn_count

    @property
    def total_trip_duration(self) -> float:
        """Get total duration of fulfilled trips."""
        return self.total_duration

    @property
    def average_trip_duration(self) -> float:
        """Calculate the average trip duration for fulfilled trips."""
        if self.fulfilled_count == 0:
            return 0.0
        return self.total_duration / self.fulfilled_count

    @property
    def total_trip_distance(self) -> float:
        """Get total trip distance for fulfilled trips."""
        return self.total_distance

    @property
    def average_trip_distance(self) -> float:
        """Calculate the average trip distance for fulfilled trips."""
        if self.fulfilled_count == 0:
            return 0.0
        return self.total_distance / self.fulfilled_count

    @property
    def average_trip_price(self) -> float:
        """Calculate the average trip price for fulfilled trips."""
        if self.fulfilled_count == 0:
            return 0.0
        return self.total_price_sum / self.fulfilled_count

    @property
    def trip_fulfillment_rate(self) -> float:
        """Calculate the trip fulfillment rate."""
        if self.total_count == 0:
            return 0.0
        return self.fulfilled_count / self.total_count

    @property
    def total_energy_consumption(self) -> float:
        """Get the total energy consumption for fulfilled trips."""
        return self.total_energy

    @property
    def average_energy_consumption(self) -> float:
        """Calculate the average energy consumption for fulfilled trips."""
        if self.fulfilled_count == 0:
            return 0.0
        return self.total_energy / self.fulfilled_count
