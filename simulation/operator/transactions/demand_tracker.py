"""
Demand tracking for each region and vehicle type.

Implements the DemandTracker class for tracking demand statistics.
"""

from collections import defaultdict
from typing import TypedDict

from simulation.environment.position import RegionId
from simulation.helper.configuration.enums import TransactionState

from .transaction import Transaction
from .transaction_listener import TransactionListener


class VehicleFlow(TypedDict):
    outflow_fulfilled: int
    outflow_missed: int
    inflow: int


VehicleDemandByRegion = dict[RegionId, dict[str, VehicleFlow]]


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
    vehicle_data : VehicleDemandByRegion
        Dictionary mapping hexagon IDs to vehicle modes and their demand statistics.
    ordered_available_vehicles : list[str]
        Vehicle mode preference order.
    """

    def __init__(self, ordered_available_vehicles: list[str]) -> None:
        self.hexagons: set[RegionId] = set()
        self.vehicle_data: VehicleDemandByRegion = defaultdict(
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
        origin: RegionId = transaction.origin
        destination: RegionId = transaction.destination
        state: TransactionState = transaction.state
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

        if state == TransactionState.FULFILLED:
            origin_stats["outflow_fulfilled"] += 1
            destination_stats["inflow"] += 1
        elif state == TransactionState.MISSED:
            origin_stats["outflow_missed"] += 1

    def get_demand_data(self) -> VehicleDemandByRegion:
        """
        Get the current demand data.

        Returns
        -------
        RegionVehicleDemand
            Dictionary mapping hexagon IDs to vehicle modes and their demand statistics.
        """
        return self.vehicle_data
