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


class TransactionLog:
    """
    Manages transaction logs for the simulation.

    Allows adding transactions, retrieving them, and converting them to a DataFrame.
    Also supports listeners that can be notified whenever a new transaction is added.

    Attributes
    ----------
    _transactions : list[Transaction]
        List of Transaction objects representing transactions.
    _df_cache : pd.DataFrame or None
        Cached DataFrame of transactions.
    _listeners : list[TransactionListener]
        List of listeners to notify on new transactions.
    _has_successful_transaction : bool
        Indicates if at least one successful transaction has occurred.
    """

    def __init__(self, listeners: list[TransactionListener] | None = None) -> None:
        self._transactions: list[Transaction] = []
        self._df_cache: pd.DataFrame | None = None
        self._listeners: list[TransactionListener] = listeners or []
        self._has_successful_transaction: bool = False
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
        """Get the metrics calculator for this transaction log."""
        return self._metrics

    @property
    def transactions(self) -> list[Transaction]:
        """
        Retrieve all transactions from the log.

        Returns
        -------
        list[Transaction]
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
        return len(self._transactions)

    @property
    def has_successful_transaction(self) -> bool:
        """
        Indicates if at least one successful transaction has occurred.

        Returns
        -------
        bool
            True if at least one transaction with state 'Fulfilled' has been added, otherwise False.
        """
        if not self._has_successful_transaction:
            for transaction in self._transactions:
                if transaction.state == TransactionState.FULFILLED:
                    self._has_successful_transaction = True
                    break
        return self._has_successful_transaction

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the transaction log to a pandas DataFrame, with caching.

        Returns
        -------
        pd.DataFrame
            DataFrame containing all transactions.
        """
        # TODO: Can we use a more efficient caching mechanism?
        if self._df_cache is not None:
            return self._df_cache
        df = pd.DataFrame([t._asdict() for t in self._transactions])
        # Expand viable_vehicle_types dict into columns
        if not df.empty and "viable_vehicle_types" in df.columns:
            types_df = pd.json_normalize(df["viable_vehicle_types"].tolist())
            df = pd.concat(
                [df.drop(columns=["viable_vehicle_types"]), types_df], axis=1
            )
        self._df_cache = df
        self._cache_size = len(self._transactions)
        return df
