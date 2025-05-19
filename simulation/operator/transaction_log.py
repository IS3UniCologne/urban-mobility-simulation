"""
Transaction management for the simulation.

This module provides functionality to record and query transactions
within the simulation environment.
"""

from typing import NamedTuple

import pandas as pd


class Transaction(NamedTuple):
    """
    Represents a single transaction record in the simulation.

    Parameters
    ----------
    vehicle_id : int | None
        Unique identifier for the vehicle. If not available, set to None.
    origin : str
        Region ID of the trip origin.
    destination : str
        Region ID of the trip destination.
    time_start : float
        Simulation time when the trip started.
    time_end : float
        Simulation time when the trip ended.
    price : float
        Price paid for the trip.
    distance : float
        Distance traveled during the trip.
    duration : float
        Duration of the trip.
    selected_vehicle_mode : str
        Name of the selected vehicle mode.
    state : str
        State of the transaction (e.g., "Fulfilled", "Missed").
    viable_vehicle_modes : dict[str, int]
        Dictionary mapping vehicle mode names to 1 (available) or 0 (not available).
    wait_time : float | None, optional
        Waiting time before the trip started (if available).
    waiting_time : float | None, optional
        Not sure why we have two of these? (if available).TODO: Figure out why we have two of these
    pick_up_time : float | None, optional
        Time spent picking up the passenger (if available).
    energy_consumption : float | None, optional
        Energy consumed during the trip (if available).
    selected_vehicle_EV : str | bool | None, optional
        Whether the selected vehicle is electric (if available).
    """

    vehicle_id: int | None
    origin: str
    destination: str
    time_start: float
    time_end: float
    price: float
    distance: float
    duration: float
    selected_vehicle_mode: str
    state: str
    viable_vehicle_modes: dict[str, int]
    wait_time: float | None = None
    waiting_time: float | None = None
    pick_up_time: float | None = None
    energy_consumption: float | None = None
    selected_vehicle_EV: str | bool | None = None


class TransactionLog:
    """
    Manages transaction logs for the simulation.

    Attributes
    ----------
    _transactions : list[Transaction]
        A list of Transaction objects representing transactions.
    """

    def __init__(self) -> None:
        self._transactions: list[Transaction] = []
        self._df_cache: pd.DataFrame | None = None

    def add_transaction(self, transaction: Transaction) -> None:
        """
        Add a transaction to the log.

        Parameters
        ----------
        transaction : Transaction
            A Transaction object containing transaction details.
        """
        self._transactions.append(transaction)
        self._df_cache = None  # Invalidate cache

    def get_transactions(self) -> list[Transaction]:
        """
        Retrieve all transactions from the log.

        Returns
        -------
        list[Transaction]
            List of all Transaction objects.
        """
        return self._transactions

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the transaction log to a pandas DataFrame, with caching.

        Returns
        -------
        pd.DataFrame
            DataFrame containing all transactions, with viable_vehicle_modes expanded.
        """
        if self._df_cache is not None:
            return self._df_cache
        df = pd.DataFrame([t._asdict() for t in self._transactions])
        # Expand viable_vehicle_modes dict into columns
        if not df.empty and "viable_vehicle_modes" in df.columns:
            modes_df = pd.json_normalize(df["viable_vehicle_modes"])
            df = pd.concat(
                [df.drop(columns=["viable_vehicle_modes"]), modes_df], axis=1
            )
        self._df_cache = df
        self._cache_size = len(self._transactions)
        return df
