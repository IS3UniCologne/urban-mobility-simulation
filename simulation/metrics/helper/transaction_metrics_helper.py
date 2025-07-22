"""Helper module for transaction-specific metrics calculations. Mainly used for OperatorMetrics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import TransactionState

if TYPE_CHECKING:
    from simulation.operator.transactions.transaction_log import TransactionLog


class TransactionMetricsHelper:
    """Calculates metrics from transaction log data."""

    def __init__(self, transaction_log: TransactionLog) -> None:
        """
        Initialize transaction metrics calculator.

        Parameters
        ----------
        transaction_log : TransactionLog
            The transaction log to analyze.
        """
        self._transaction_log = transaction_log

    @property
    def total_revenue(self) -> float:
        """
        Calculate the total revenue from all fulfilled transactions.

        This method uses the cached DataFrame for vectorized operations.
        If we need access to this function frequently during the simulation, we might want to change it.

        Returns
        -------
        float
            Total revenue from transactions with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "price"].sum())

    @property
    def total_fulfilled_trips(self) -> int:
        """
        Get the total number of fulfilled trips.

        Returns
        -------
        int
            Count of transactions with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        return int(df[df["state"] == TransactionState.FULFILLED].shape[0])

    @property
    def total_missed_trips(self) -> int:
        """
        Get the total number of missed trips.

        Returns
        -------
        int
            Count of transactions with state 'Missed'.
        """
        df = self._transaction_log.to_dataframe()
        # TODO: Terminology Missed vs Withdrawn is a bit confusing here.

        return int(
            df[
                df["state"].isin([TransactionState.MISSED, TransactionState.WITHDRAWN])
            ].shape[0]
        )

    @property
    def total_missed_revenue(self) -> float:
        """
        Calculate the total revenue lost from missed trips.

        Returns
        -------
        float
            Total revenue from transactions with state 'Missed'.
        """
        df = self._transaction_log.to_dataframe()
        missed_mask = df["state"] == TransactionState.MISSED
        return float(df.loc[missed_mask, "price"].sum())

    @property
    def total_trip_duration(self) -> float:
        """
        Calculate the total duration of all fulfilled trips.

        Returns
        -------
        float
            Total duration of trips with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "duration"].sum())

    @property
    def average_trip_duration(self) -> float:
        """
        Calculate the average trip duration for fulfilled trips.

        Returns
        -------
        float
            Average duration of trips with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "duration"].mean())

    @property
    def total_trip_distance(self) -> float:
        """
        Calculate the total trip distance for fulfilled trips.

        Returns
        -------
        float
            Total distance of trips with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "distance"].sum())

    @property
    def average_trip_distance(self) -> float:
        """
        Calculate the average trip distance for fulfilled trips.

        Returns
        -------
        float
            Average distance of trips with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "distance"].mean())

    @property
    def average_trip_price(self) -> float:
        """
        Calculate the average trip price for fulfilled trips.

        Returns
        -------
        float
            Average price of trips with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "price"].mean())

    @property
    def trip_fulfillment_rate(self) -> float:
        """
        Calculate the trip fulfillment rate.

        Returns
        -------
        float
            Ratio of fulfilled trips to total trips.
        """
        total_trips = self._transaction_log.transaction_count
        if total_trips == 0:
            return 0.0
        return self.total_fulfilled_trips / total_trips

    @property
    def total_energy_consumption(self) -> float:
        """
        Calculate the total energy consumption for all fulfilled trips.

        Returns
        -------
        float
            Total energy consumed during trips with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "energy_consumption"].sum())

    @property
    def average_energy_consumption(self) -> float:
        """
        Calculate the average energy consumption for fulfilled trips.

        Returns
        -------
        float
            Average energy consumed during trips with state 'Fulfilled'.
        """
        df = self._transaction_log.to_dataframe()
        fulfilled_mask = df["state"] == TransactionState.FULFILLED
        return float(df.loc[fulfilled_mask, "energy_consumption"].mean())
