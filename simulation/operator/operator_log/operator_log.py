"""Operator log keeps track of transactions from the operators' point of view."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from simulation.metrics.statistics.operator_log_stats import OperatorLogStats

if TYPE_CHECKING:
    from .operator_log_entry import OperatorLogEntry
    from .operator_log_entry_listener import OperatorLogEntryListener


class OperatorLog:
    """
    Keeps track of transactions from the operators' point of view.

    Allows adding transactions, retrieving them, and converting them to a DataFrame.
    Also supports listeners that can be notified whenever a new transaction is added.

    Parameters
    ----------
    listeners : list of OperatorLogEntryListener, optional
        Initial listeners to be notified of new transactions. Default is None.

    Attributes
    ----------
    _transactions : list of OperatorLogEntry objects
        List of OperatorLogEntry objects representing transactions.
    _df_cache : pandas DataFrame or None
        Cached DataFrame of transactions.
    _listeners : list of OperatorLogEntryListener objects
        List of listeners to notify on new transactions.
    metrics : OperatorLogStats
        Metrics tracker.
    """

    def __init__(self, listeners: list[OperatorLogEntryListener] | None = None) -> None:
        self._transactions: list[OperatorLogEntry] = []
        self._df_cache: pd.DataFrame | None = None
        self._listeners: list[OperatorLogEntryListener] = listeners or []
        self.metrics = OperatorLogStats()

    def add_transaction(self, transaction: OperatorLogEntry) -> None:
        """
        Add a transaction to the log.

        Parameters
        ----------
        transaction : OperatorLogEntry
            An OperatorLogEntry object containing transaction details.

        """
        self._transactions.append(transaction)
        self._df_cache = None  # Invalidate cache

        # Update incremental metrics
        self.metrics.on_transaction(transaction)

        # Notify listeners
        for listener in self._listeners:
            listener.on_transaction(transaction)

    def add_listener(self, listener: OperatorLogEntryListener) -> None:
        """
        Add a listener to be notified of new transactions.

        Parameters
        ----------
        listener : OperatorLogEntryListener
            The listener to add.

        Returns
        -------
        None
        """
        self._listeners.append(listener)

    @property
    def transactions(self) -> list[OperatorLogEntry]:
        """
        Retrieve all transactions from the log.

        Returns
        -------
        list of OperatorLogEntry objects
            List of all OperatorLogEntry objects.
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
        return self.metrics.total_count

    @property
    def has_successful_transaction(self) -> bool:
        """
        Indicates if at least one successful transaction has occurred.

        Returns
        -------
        bool
            True if at least one transaction with state 'Fulfilled' has been added, otherwise False.
        """
        return self.metrics.has_fulfilled

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the transaction log to a pandas DataFrame.

        Results are cached until a new transaction is added.

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
