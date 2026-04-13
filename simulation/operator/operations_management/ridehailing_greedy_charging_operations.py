from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

import h3
import pandas as pd
from beartype.door import is_bearable
from simpy import AnyOf

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
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


class RideHailingGreedyChargingOperations(RideHailingOperations):
    """Naive, greedy charging operations for ride hailing operators.

    .. deprecated::
        Use ``CompetitiveChargingOperations`` with a ``GreedyClosestAvailable``
        strategy instead.  This class will be removed in a future version.

    This class implements a myopic, greedy charging strategy for ride hailing operators based on available charging stations at the moment of execution.
    If queueing at charging stations is not allowed, lowest SOC vehicles are sent to closest charging stations until capacity is exhausted.
    TODO: If queueing is allowed, lowest SOC vehicles are sent to charging stations that minimize the total time (travel + (queue-travel) + charging).
    """

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)

        self._base_buffer = h3.average_hexagon_edge_length(
            deps.sim.config.world.SPATIAL_RESOLUTION - 1, unit="m"
        )  # use a buffer when calculating distances to charging stations of next coarser grid level edge length (radius)

        self._recharge_threshold = self._config.RECHARGE_THRESHOLD

        self._allow_queue = self._config.ALLOWED_QUEUE_SIZE > 0

        self._job_transactions: list[dict] = []

        # Events
        self._charging_plan_updated = self._sim.env.event()
        self._job_executed = self._sim.env.event()

        # When to start operations
        self._time_between_operations = self._config.TIME_BETWEEN_OPERATIONS

        # Shift Duration
        self._duration_of_operations = self._config.OPERATIONS_DURATION

    @property
    def charging_plan_updated(self):  # noqa: ANN201, D102
        return self._charging_plan_updated

    @property
    def job_executed(self):  # noqa: ANN201, D102
        return self._job_executed

    @property
    def job_transactions(self):  # noqa: ANN201, D102
        return pd.DataFrame(self._job_transactions)

    def execute(self) -> Generator[Timeout, None, None]:
        """Run main loop of greedy lowest-soc, closest-charging-station operations.

        Yields
        ------
        Generator[Timeout, None, None]
            _description_
        """
        while True:
            yield self._env.timeout(self._time_between_operations)

            # 0. reset charging sessions
            scheduled_sessions: list[ChargingSession] = []

            # 1. Fetch vehicles that need to be charged
            vehicles_to_charge = self._operator.fleet.mark_vehicles_to_be_charged(
                self._recharge_threshold
            )

            self.logger.debug(
                "There are %s vehicles currently below SOC threshold and an additional %s after task completion.",
                self._operator.fleet.count_vehicles_below_soc_level(
                    self._recharge_threshold
                ),
                len(vehicles_to_charge),
            )

            if not vehicles_to_charge:
                continue

            vehicles_to_charge = sorted(
                vehicles_to_charge, key=lambda x: x.energy_system.predicted_energy
            )

            # 2. Fetch charging station availabilities
            # 2.a Account for the possibility that there is no charging station available (could happen in coordinated shared infrastructure, e.g.)
            if not self._operator.charging_infrastructure.get_locations():
                self.logger.info(
                    "No charging stations available. No charging plan generated."
                )
                continue

            # 2.b Get latest known capacity
            # for virtual CS, we can use the capacity, as it gets updated
            capacity_to_consider: dict[str, int] = {}
            if is_bearable(
                self._operator.charging_infrastructure, VirtualChargingInfrastructure
            ):
                capacity_to_consider = {
                    x.location: x.capacity
                    for x in self._operator.charging_infrastructure.charging_stations
                    if x.capacity > 0
                }
            else:
                # otherwise we need to consider capacity minus current plugged in vehicles:
                capacity_to_consider = {
                    x.location: x.capacity - len(x.plugs.users)
                    for x in self._operator.charging_infrastructure.charging_stations
                    if x.capacity - len(x.plugs.users) > 0
                }

            # 2.c early stop if all charging stations are out of capacity and queueing is disallowed5
            if not capacity_to_consider and not self._allow_queue:
                self.logger.info(
                    "No charging stations available and queueing disallowed. No charging plan generated."
                )
                continue

            # 3. Assign vehicles to charging stations, greedily by closest available
            for vehicle in vehicles_to_charge:
                # 3.a get region of vehicle at destination (if moving) or current position (if not moving)
                region = vehicle.destination.get_region_id()

                # 3.b get distances of charging stations
                # considering only the ones with remaining capacity from other charging plans
                sorted_cs_list = self._distance_matrix.loc[
                    list(capacity_to_consider.keys())
                ][[region]].sort_values(by=region, ascending=True)

                if sorted_cs_list.empty:
                    # no charging stations available because capacity exhausted
                    self.logger.debug(
                        "Reserved capacity at all charging stations exhausted, skipping creation of charging tasks after %s tasks were created.",
                        len(scheduled_sessions),
                    )
                    break

                # 3.c select closest charging station
                selected_cs_location = sorted_cs_list.index[0]
                selected_cs = self._operator.charging_infrastructure.get_charging_station_by_location(
                    selected_cs_location
                )
                selected_cs_distance = sorted_cs_list.iat[0, 0] + self._base_buffer

                # 3.d check if reachable
                if not vehicle.energy_system.has_enough_energy(
                    distance=selected_cs_distance, use_buffer=False
                ):
                    # TODO: track how often this happens - interesting metric for allocation efficiency/effectiveness
                    self.logger.debug(
                        "Vehicle %s considered for charging at %s has not enough state of charge to relocate there, skipping.",
                        vehicle.uid,
                        selected_cs,
                    )
                    continue

                # 3.e create ChargingSession
                # we need to do some differentiation here, because we need to check if the charging station is virtual, and if it is, we need to check if we are in a context with reserved timeslots
                scheduled_time = None
                if is_bearable(selected_cs, VirtualChargingStation):
                    scheduled_time = selected_cs.valid_timeframe
                    try:
                        scheduled_time = scheduled_time[0]
                    except TypeError:
                        # 'NoneType' object is not subscriptable > not using reservation timeslots
                        scheduled_time = None

                session = ChargingSession.create(
                    sim=self._sim,
                    vehicle=vehicle,
                    charging_station=selected_cs,
                    scheduled_time=scheduled_time,
                )

                scheduled_sessions.append(session)

                # Track session completion
                self._env.process(self._track_session(session))

                # 3.f Update known capacity
                capacity_to_consider[selected_cs_location] -= 1
                if capacity_to_consider[selected_cs_location] == 0:
                    del capacity_to_consider[selected_cs_location]

            # 4. Execute scheduled charging sessions
            self.logger.debug(
                "Charging sessions scheduled: %s.", len(scheduled_sessions)
            )
            # Notify listeners
            self._charging_plan_updated.succeed()
            self._charging_plan_updated = self._env.event()

            for session in scheduled_sessions:
                self.logger.debug(
                    "Processing charging session for vehicle %s.", session.vehicle.uid
                )
                self._env.process(self._execute_autonomous_charging_session(session))
                self._job_executed.succeed(session)
                self._job_executed = self._env.event()

    def _track_session(self, session: ChargingSession) -> Generator[AnyOf, Any, None]:
        yield AnyOf(self._env, [session.finished, self._world.simulation_finished])

        # TODO: This should use new transactions
        self._job_transactions.append(
            {
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
            }
        )
