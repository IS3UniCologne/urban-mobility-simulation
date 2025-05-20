"""
Transaction management for the simulation.

This module provides functionality to record and query transactions
within the simulation environment.
"""

from collections import defaultdict
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
        Not sure why we have two of these? (if available).TODO: Straighten this out #50
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


class TransactionListener:
    """
    Base class for transaction listeners.

    Subclass this and override on_transaction to listen for new transactions.

    Methods
    -------
    on_transaction(transaction: Transaction) -> None
        Called when a new transaction is added.
    """

    def on_transaction(self, transaction: Transaction) -> None:
        """
        Listen for a new transaction.

        Parameters
        ----------
        transaction : Transaction
            The transaction that was added.
        """


class TransactionLog:
    """
    Manages transaction logs for the simulation.

    Attributes
    ----------
    _transactions : list[Transaction]
        A list of Transaction objects representing transactions.
    """

    def __init__(self, listeners: list[TransactionListener] | None = None) -> None:
        self._transactions: list[Transaction] = []
        self._df_cache: pd.DataFrame | None = None
        self._listeners: list[TransactionListener] = listeners or []
        self._has_successful_transaction: bool = False

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
        for listener in self._listeners:
            listener.on_transaction(transaction)

    def add_listener(self, listener: TransactionListener) -> None:
        """
        Add a listener to be notified of new transactions.

        Parameters
        ----------
        listener : TransactionListener
            The listener to add.
        """
        self._listeners.append(listener)

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
                if transaction.state == "Fulfilled":
                    self._has_successful_transaction = True
                    break
        return self._has_successful_transaction

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


class DemandTracker(TransactionListener):
    """
    Tracks demand statistics for each region and vehicle type.

    Parameters
    ----------
    ordered_available_vehicles : list[str]
        List of vehicle modes in order of preference.

    Attributes
    ----------
    hexagons : set[str]
        Set of all hexagon IDs seen so far.
    vehicle_data : dict[str, dict[str, dict[str, int]]]
        Nested dictionary: hex_id -> vehicle_type -> flow_type -> count.
    ordered_available_vehicles : list[str]
        Vehicle mode preference order.
    """

    def __init__(self, ordered_available_vehicles: list[str]) -> None:
        self.hexagons: set[str] = set()
        self.vehicle_data: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: defaultdict(
                lambda: {"outflow_fulfilled": 0, "outflow_missed": 0, "inflow": 0}
            )
        )
        self.ordered_available_vehicle = ordered_available_vehicles

    def on_transaction(self, transaction: Transaction) -> None:
        """
        Update demand statistics for a transaction.

        Parameters
        ----------
        transaction : Transaction
            The transaction that was added.
        """
        origin: str = transaction.origin
        destination: str = transaction.destination
        state: str = transaction.state
        viable_vehicle_modes: dict[str, int] = transaction.viable_vehicle_modes

        self.hexagons.add(origin)
        self.hexagons.add(destination)

        preferred_vehicle: str | None = next(
            (
                vehicle
                for vehicle in self.ordered_available_vehicle
                if viable_vehicle_modes.get(vehicle, 0) == 1
            ),
            None,
        )
        if preferred_vehicle is None:
            return

        origin_stats = self.vehicle_data[origin][preferred_vehicle]
        destination_stats = self.vehicle_data[destination][preferred_vehicle]

        if state == "Fulfilled":
            origin_stats["outflow_fulfilled"] += 1
            destination_stats["inflow"] += 1
        elif state == "Missed":
            origin_stats["outflow_missed"] += 1

    def get_demand_data(self) -> dict:
        """
        Get the current demand data.

        Returns
        -------
        dict
            Nested dictionary with demand statistics.
        """
        return {"hexagons": self.hexagons, "vehicle_data": self.vehicle_data}
