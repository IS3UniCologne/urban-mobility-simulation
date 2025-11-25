"""
Transaction log management for the simulation.

Implements the TransactionLog class for recording and querying transactions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from simulation.helper.configuration.enums import TransactionState
from simulation.metrics.helper.transaction_metrics_helper import (
    TransactionMetricsHelper,
)

if TYPE_CHECKING:
    from .transaction import Transaction
    from .transaction_listener import TransactionListener


class _TransactionLogAccumulator:
    """
    Internal class to accumulate incremental metrics for the TransactionLog.

    This allows for O(1) access to common metrics.
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
        "total_revenue",
        "withdrawn_count",
    )

    def __init__(self) -> None:
        self.total_count = 0
        self.fulfilled_count = 0
        self.missed_count = 0
        self.withdrawn_count = 0
        self.total_revenue = 0.0
        self.total_missed_revenue = 0.0
        self.total_duration = 0.0
        self.total_distance = 0.0
        self.total_energy = 0.0
        self.total_price_sum = 0.0
        self.has_fulfilled = False

    def on_transaction(self, transaction: Transaction) -> None:
        """
        Update metrics when a transaction is added.

        Parameters
        ----------
        transaction : Transaction
            The transaction to use for updating the incremental metrics.
        """
        self.total_count += 1

        if transaction.state == TransactionState.FULFILLED:
            self.fulfilled_count += 1
            self.has_fulfilled = True
            self.total_revenue += transaction.revenue
            self.total_price_sum += transaction.price
            self.total_duration += transaction.duration
            self.total_distance += transaction.distance
            if transaction.energy_consumption is not None:
                self.total_energy += transaction.energy_consumption

        elif transaction.state == TransactionState.MISSED:
            self.missed_count += 1
            self.total_missed_revenue += transaction.price

        elif transaction.state == TransactionState.WITHDRAWN:
            self.withdrawn_count += 1


class TransactionLog:
    """
    Manages transaction logs for the simulation.

    Allows adding transactions, retrieving them, and converting them to a DataFrame.
    Also supports listeners that can be notified whenever a new transaction is added.

    Parameters
    ----------
    listeners : list of TransactionListener or None, optional
        Initial listeners to be notified of new transactions. Default is None.
    max_window_size : int, optional
        Maximum number of entries to keep in a window. Default is 100.

    Attributes
    ----------
    _transactions : list of Transaction objects
        List of Transaction objects representing transactions.
    _df_cache : pandas DataFrame or None
        Cached DataFrame of transactions.
    _listeners : list of TransactionListener objects
        List of listeners to notify on new transactions.
    _incremental_metrics : _TransactionLogAccumulator
        Internal incremental metrics tracker.
    _metrics : TransactionMetricsHelper object
        Public metrics helper interface.
    """

    def __init__(
        self,
        listeners: list[TransactionListener] | None = None,
        max_window_size: int = 100,
    ) -> None:
        self._transactions: list[Transaction] = []
        self._df_cache: pd.DataFrame | None = None
        self._listeners: list[TransactionListener] = listeners or []
        self._incremental_metrics = _TransactionLogAccumulator()

        self._metrics = TransactionMetricsHelper(self)

    def add_transaction(self, transaction: Transaction) -> None:
        """
        Add a transaction to the log.

        Parameters
        ----------
        transaction : Transaction
            A Transaction object containing transaction details.

        Returns
        -------
        None
        """
        self._transactions.append(transaction)
        self._df_cache = None  # Invalidate cache

        # Update incremental metrics
        self._incremental_metrics.on_transaction(transaction)

        # Notify listeners
        for listener in self._listeners:
            listener.on_transaction(transaction)

    def add_listener(self, listener: TransactionListener) -> None:
        """
        Add a listener to be notified of new transactions.

        Parameters
        ----------
        listener : TransactionListener
            The listener to add.

        Returns
        -------
        None
        """
        self._listeners.append(listener)

    @property
    def metrics(self) -> TransactionMetricsHelper:
        """
        Get the metrics helper for this transaction log.

        Returns
        -------
        TransactionMetricsHelper object
            Metrics helper with O(1) property access via incremental tracking.
        """
        return self._metrics

    @property
    def incremental_metrics(self) -> _TransactionLogAccumulator:
        """
        Get the internal incremental metrics tracker.

        This is used internally by TransactionMetricsHelper for O(1) access.

        Returns
        -------
        _TransactionLogAccumulator
            Internal accumulator object tracking incremental metrics.
        """
        return self._incremental_metrics

    @property
    def transactions(self) -> list[Transaction]:
        """
        Retrieve all transactions from the log.

        Returns
        -------
        list of Transaction objects
            List of all Transaction objects.
        """
        return self._transactions

    @property
    def transaction_count(self) -> int:
        """
        Get the number of transactions in the log.

        Returns
        -------
        int
            Number of transactions.
        """
        return self._incremental_metrics.total_count

    @property
    def has_successful_transaction(self) -> bool:
        """
        Indicates if at least one successful transaction has occurred.

        Returns
        -------
        bool
            True if at least one transaction with state 'Fulfilled' has been added, otherwise False.
        """
        return self._incremental_metrics.has_fulfilled

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the transaction log to a pandas DataFrame, with caching.

        Returns
        -------
        pandas DataFrame
            DataFrame containing all transactions. Returns an empty DataFrame if no transactions are present.
        """
        if self._df_cache is not None:
            # Cache is invalidated on new transaction addition
            return self._df_cache

        if not self._transactions:
            return pd.DataFrame()

        df = pd.DataFrame([t._asdict() for t in self._transactions])

        # Expand accepted_vehicle_types set into individual boolean columns
        df = self._expand_accepted_vehicle_types(df)

        self._df_cache = df
        return df

    def _expand_accepted_vehicle_types(self, df: pd.DataFrame) -> pd.DataFrame:
        if "accepted_vehicle_types" in df.columns:
            types_list = [
                {v_type: True for v_type in t} for t in df["accepted_vehicle_types"]
            ]
            types_df = pd.DataFrame(types_list).fillna(False)
            types_df = types_df.add_suffix("_accepted")
            df = pd.concat(
                [df.drop(columns=["accepted_vehicle_types"]), types_df], axis=1
            )

        return df
