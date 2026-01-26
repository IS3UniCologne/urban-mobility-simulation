"""
Demand tracking for each region and vehicle type.

Listens for operator log entries to keep a running tally of demand.
"""

from collections import defaultdict
from typing import TypedDict

from simulation.context.simulation_context import SimulationContext
from simulation.helper.enums import VehicleType
from simulation.helper.types import RegionId

from .operator_log_entry import (
    FulfilledOperatorLogEntry,
    MissedOperatorLogEntry,
    OperatorLogEntry,
)
from .operator_log_entry_listener import OperatorLogEntryListener


class VehicleFlow(TypedDict):  # noqa: D101
    outflow_fulfilled: int
    outflow_missed: int
    inflow: int


VehicleDemandByRegion = dict[RegionId, dict[VehicleType, VehicleFlow]]


class DemandMonitor(OperatorLogEntryListener):
    """
    Tracks demand statistics for each region and vehicle type.

    Attributes
    ----------
    hexagons : set[str]
        Set of all hexagon IDs seen so far.
    vehicle_data : VehicleDemandByRegion
        Dictionary mapping hexagon IDs to vehicle modes and their demand statistics.

    """

    def __init__(self, sim: SimulationContext) -> None:
        self.hexagons: set[RegionId] = set()
        self.vehicle_data: VehicleDemandByRegion = defaultdict(
            lambda: defaultdict(
                lambda: {"outflow_fulfilled": 0, "outflow_missed": 0, "inflow": 0}
            )
        )
        self._rng = sim.random_manager.get_rng("DEMAND_MONITOR")

    def on_transaction(self, transaction: OperatorLogEntry) -> None:
        """
        Update demand statistics for a transaction.

        Parameters
        ----------
        transaction : OperatorLogEntry
            The transaction that was added.

        Returns
        -------
        None
        """
        origin: RegionId = transaction.origin
        destination: RegionId = transaction.destination

        self.hexagons.add(origin)
        self.hexagons.add(destination)

        if isinstance(transaction, FulfilledOperatorLogEntry):
            vehicle_type = transaction.selected_vehicle_type
            self.vehicle_data[origin][vehicle_type]["outflow_fulfilled"] += 1
            self.vehicle_data[destination][vehicle_type]["inflow"] += 1
        elif isinstance(transaction, MissedOperatorLogEntry):
            # TODO: Find a better way to do this, for now this should be approximately correct over time :)
            vehicle_type = self._rng.choice(
                sorted(list(transaction.accepted_vehicle_types))
            )
            self.vehicle_data[origin][vehicle_type]["outflow_missed"] += 1

    def get_demand_data(self) -> VehicleDemandByRegion:
        """
        Get the current demand data.

        Returns
        -------
        RegionVehicleDemand
            Dictionary mapping hexagon IDs to vehicle modes and their demand statistics.
        """
        return self.vehicle_data
