"""Helper module for transaction-specific metrics calculations. Mainly used for OperatorMetrics."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.operator.transactions.transaction_log import TransactionLog


class TransactionMetricsHelper:
    """
    Calculates metrics from transaction log data.

    Parameters
    ----------
    transaction_log : TransactionLog
        The transaction log to analyze.

    Attributes
    ----------
    _transaction_log : TransactionLog
        The transaction log used for metrics calculations.
    """

    def __init__(self, transaction_log: TransactionLog) -> None:
        """Initialize self."""
        self._transaction_log = transaction_log

    @property
    def total_revenue(self) -> float:
        """
        Get total revenue from fulfilled transactions.

        Returns
        -------
        float
            Total revenue from transactions with state 'Fulfilled'.
        """
        return self._transaction_log.incremental_metrics.total_revenue

    @property
    def total_fulfilled_trips(self) -> int:
        """
        Get the total number of fulfilled trips.

        Returns
        -------
        int
            Count of transactions with state 'Fulfilled'.
        """
        return self._transaction_log.incremental_metrics.fulfilled_count

    @property
    def total_missed_trips(self) -> int:
        """
        Get the total number of missed trips.

        Returns
        -------
        int
            Count of transactions with state 'Missed' or 'Withdrawn'.
        """
        metrics = self._transaction_log.incremental_metrics
        return metrics.missed_count + metrics.withdrawn_count

    @property
    def total_missed_revenue(self) -> float:
        """
        Get total revenue lost from missed trips.

        Returns
        -------
        float
            Total revenue from transactions with state 'Missed'.
        """
        return self._transaction_log.incremental_metrics.total_missed_revenue

    @property
    def total_trip_duration(self) -> float:
        """
        Get total duration of fulfilled trips.

        Returns
        -------
        float
            Total duration of trips with state 'Fulfilled'.
        """
        return self._transaction_log.incremental_metrics.total_duration

    @property
    def average_trip_duration(self) -> float:
        """
        Calculate the average trip duration for fulfilled trips.

        Returns
        -------
        float
            Average duration of trips with state 'Fulfilled'.
            If no fulfilled trips exist, returns 0.0.
        """
        metrics = self._transaction_log.incremental_metrics
        if metrics.fulfilled_count == 0:
            return 0.0
        return metrics.total_duration / metrics.fulfilled_count

    @property
    def total_trip_distance(self) -> float:
        """
        Get total trip distance for fulfilled trips.

        Returns
        -------
        float
            Total distance of trips with state 'Fulfilled'.
        """
        return self._transaction_log.incremental_metrics.total_distance

    @property
    def average_trip_distance(self) -> float:
        """
        Calculate the average trip distance for fulfilled trips.

        Returns
        -------
        float
            Average distance of trips with state 'Fulfilled'.
            If no fulfilled trips exist, returns 0.0.
        """
        metrics = self._transaction_log.incremental_metrics
        if metrics.fulfilled_count == 0:
            return 0.0
        return metrics.total_distance / metrics.fulfilled_count

    @property
    def average_trip_price(self) -> float:
        """
        Calculate the average trip price for fulfilled trips.

        Returns
        -------
        float
            Average price of trips with state 'Fulfilled'.
            If no fulfilled trips exist, returns 0.0.
        """
        metrics = self._transaction_log.incremental_metrics
        if metrics.fulfilled_count == 0:
            return 0.0
        return metrics.total_price_sum / metrics.fulfilled_count

    @property
    def trip_fulfillment_rate(self) -> float:
        """
        Calculate the trip fulfillment rate.

        Returns
        -------
        float
            Ratio of fulfilled trips to total trips.
            Returns 0.0 if there are no transactions.
        """
        metrics = self._transaction_log.incremental_metrics
        if metrics.total_count == 0:
            return 0.0
        return metrics.fulfilled_count / metrics.total_count

    @property
    def total_energy_consumption(self) -> float:
        """
        Get the total energy consumption for fulfilled trips.

        Returns
        -------
        float
            Total energy consumed during trips with state 'Fulfilled'.
        """
        return self._transaction_log.incremental_metrics.total_energy

    @property
    def average_energy_consumption(self) -> float:
        """
        Calculate the average energy consumption for fulfilled trips.

        Returns
        -------
        float
            Average energy consumed during trips with state 'Fulfilled'.
            If no fulfilled trips exist, returns 0.0.
        """
        metrics = self._transaction_log.incremental_metrics
        if metrics.fulfilled_count == 0:
            return 0.0
        return metrics.total_energy / metrics.fulfilled_count
