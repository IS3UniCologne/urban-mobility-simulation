"""
Demand tracking for each region and vehicle type.

Implements the DemandTracker class for tracking demand statistics.
"""

from collections import defaultdict

from .transaction import Transaction
from .transaction_listener import TransactionListener


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
        self.ordered_available_vehicles = ordered_available_vehicles

    def on_transaction(self, transaction: Transaction) -> None:
        """
        Update demand statistics for a transaction.

        Parameters
        ----------
        transaction : Transaction
            The transaction that was added.

        Returns
        -------
        None
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
                for vehicle in self.ordered_available_vehicles
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
            Dictionary with keys:
            - "hexagons": set[str], all hexagon IDs seen so far.
            - "vehicle_data": dict[str, dict[str, dict[str, int]]], demand statistics.
        """
        return {"hexagons": self.hexagons, "vehicle_data": self.vehicle_data}
