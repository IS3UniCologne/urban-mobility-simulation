from __future__ import annotations

from typing import TYPE_CHECKING, Any
import pandas as pd
from beartype.door import is_bearable
from simpy import AnyOf

from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)
from simulation.operator.data_transfer_object import ChargingSession
from simulation.operator.operations_management.ride_hailing_operations import (
    RideHailingOperations,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from simpy.events import Timeout
    from simulation.operator.operations_management.operations import (
        OperationsDependencies,
    )


class RideHailingExplicitChargingOperations(RideHailingOperations):
    """Executes externally supplied vehicle-to-station allocations inside the SimPy event loop."""

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)
        self._job_transactions: list[dict] = []
        
        # Core synchronization events
        self._charging_plan_updated = self._sim.env.event()
        self._job_executed = self._sim.env.event()

    @property
    def charging_plan_updated(self):
        return self._charging_plan_updated

    @property
    def job_executed(self):
        return self._job_executed

    @property
    def job_transactions(self):
        return pd.DataFrame(self._job_transactions)

    def execute(self, pairs: dict[int, str]) -> Generator[Timeout, None, None]:
        """Processes the explicit vehicle_id to station_location mapping matrix."""
        scheduled_sessions: list[ChargingSession] = []

        if not pairs:
            self.logger.debug("No external charging allocations passed for this execution tick.")
            return

        # 1. Process and map structural pairings to live memory instancses
        for vehicle_uid, station_location in list(pairs.items()):
            try:
                # Resolves the index directly against the physical fleet list
                vehicle = next(vehicle for vehicle in self._operator.fleet.vehicles if vehicle.uid == vehicle_uid)
            except IndexError:
                self.logger.warning("Vehicle index %s out of fleet bounds. Skipping.", vehicle_uid)
                continue

            # Resolve physical or virtual station tracking node
            selected_cs = self._operator.charging_infrastructure.get_charging_station_by_location(
                station_location
            )
            if not selected_cs:
                self.logger.warning("Station node %s missing from infra. Skipping pair.", station_location)
                continue

            # 2. Handle virtual slot reservations time horizons
            scheduled_time = None
            if is_bearable(selected_cs, VirtualChargingStation):
                scheduled_time = selected_cs.valid_timeframe
                try:
                    scheduled_time = scheduled_time[0]
                except (TypeError, IndexError):
                    scheduled_time = None

            # 3. Bind instances into standard state data transfer object
            session = ChargingSession.create(
                sim=self._sim,
                vehicle=vehicle,
                charging_station=selected_cs,
                scheduled_time=scheduled_time,
            )

            scheduled_sessions.append(session)
            self._env.process(self._track_session(session))

        # 4. Dispatch assignments to background simulation process stack
        if scheduled_sessions:
            self.logger.info("Executing %s explicit charging assignments.", len(scheduled_sessions))
            self._charging_plan_updated.succeed()
            self._charging_plan_updated = self._env.event()

            for session in scheduled_sessions:
                self._job_executed.succeed(session)
                self._job_executed = self._env.event()
                self._env.process(self._execute_autonomous_charging_session(session))
                
        # Required zero-time yield to conform to SimPy's process signature requirements
        yield self._env.timeout(0)

    def _track_session(self, session: ChargingSession) -> Generator[AnyOf, Any, None]:
        """Maintains structural transactional histories once actors complete their task."""
        yield AnyOf(self._env, [session.finished, self._world.simulation_finished])
        self._job_transactions.append({
            "start_time": session.start_time,
            "estimated_arrival_time": session.estimated_arrival_time,
            "scheduled_time": session.scheduled_time,
            "end_time": self._env.now,
            "vehicle": session.vehicle.uid,
            "fleet": session.vehicle.fleet.uid,
            "charging_station": session.charging_station.location,
            "waiting_time": session.waiting_time,
            "charging_duration": session.charging_duration,
            "estimated_completion_time": session.estimated_completion_time,
            "kWh_charged": session.kWh_charged,
        })