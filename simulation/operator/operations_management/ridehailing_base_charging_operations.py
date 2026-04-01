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

    from simulation.operator.operations_management.operations import (
        OperationsDependencies,
    )
    from simulation.vehicle.vehicle import Vehicle


class RideHailingBaseChargingOperations(RideHailingOperations):  # noqa: D101
    __slots__ = (
        "_allow_queue",
        "_available_modes",
        "_base_buffer",
        "_charging_plan_updated",
        "_config",
        "_distance_matrix",
        "_duration_of_operations",
        "_job_executed",
        "_job_transactions",
        "_operation_duration",
        "_operations_started",
        "_operator",
        "_recharge_threshold",
        "_sim",
        "_time_between_operations",
        "_world",
    )

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)

        self._base_buffer = h3.average_hexagon_edge_length(
            deps.sim.config.world.SPATIAL_RESOLUTION - 1, unit="m"
        )  # use a buffer when calculating distances to charging stations of next coarser grid level edge length (radius)

        self._recharge_threshold = self._config.RECHARGE_THRESHOLD

        self._allow_queue = self._config.ALLOW_QUEUE

        self._job_transactions: list[dict] = []

        # Events
        self._charging_plan_updated = self._sim.env.event()
        self._operations_started = self._sim.env.event()
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

    def execute(self):  # noqa: ANN201
        """Below, we combine the old operational logic from operations_ridehailing.py and rebalancing_scheduler_ridehailing.py"""  # noqa: D400
        while True:
            yield self._env.timeout(self._time_between_operations)

            # Retrieve Vehicle Transactions
            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans = self.generate_charging_plan()

            if not charging_plans:
                continue

            scheduled_sessions: list[ChargingSession] = []
            for charging_plan in charging_plans:
                *_, charging_station, vehicle = charging_plan[0]

                # we need to do some differentiation here, because we need to check if the charging station is virtual, and if it is, we need to check if we are in a context with reserved timeslots
                scheduled_time = None
                if is_bearable(charging_station, VirtualChargingStation):
                    scheduled_time = charging_station.valid_timeframe
                    try:
                        scheduled_time = scheduled_time[0]
                    except TypeError:
                        # 'NoneType' object is not subscriptable > not using reservation timeslots
                        scheduled_time = None

                session = ChargingSession.create(
                    sim=self._sim,
                    vehicle=vehicle,
                    charging_station=charging_station,
                    scheduled_time=scheduled_time,
                )

                scheduled_sessions.append(session)

                # Track session completion
                self._env.process(self._track_session(session))

            self.logger.info(
                "There are %s vehicles with low state of charge.",
                self._operator.fleet.count_vehicles_below_soc_level(
                    self._recharge_threshold
                ),
            )

            self.logger.info(
                "Charging sessions scheduled. In total %s are generated.",
                len(charging_plans),
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

    def generate_charging_plan(self):  # noqa: ANN201
        """
        Generate a rule based charging plan based on given service worker capacity
        :return: **charging_plan**: Dictionary with keys for vehicle modes and values with lists of multiple
                charging tasks
                **used_capacity**: How many service workers are planned to cope with charging needs
        """  # noqa: D205, D400
        # Get Current Fleet State
        vehicles_to_charge = self._operator.fleet.mark_vehicles_to_be_charged(
            self._recharge_threshold
        )
        # if config.settings.PERSIST_RESULTS:
        #     state.to_csv(os.path.join(config.output_path, config.fleet_state_file), index = False)

        charging_plans = self.calculate_charging_plan(vehicles_to_charge)

        return charging_plans

    def calculate_charging_plan(self, vehicles_to_charge: list[Vehicle]):  # noqa: ANN201
        """
        :param vehicles_to_charge: List of vehicles to be charged
        :return: all_charging_plans and used capacity per mode
                all_charging_plans {"SharedKickScooter":[[(origin, destination, number of vehicles to pick up, destination to base), ()], [()],
                                    "SharedScooter": [], "SharedCar":[]}
                used_capacity = [1, 3, 5] => per available vehicle mode returns number of service workers assigned to charge these vehicles
                                          => 1 SW for Kick Scooter, 3 for Shared Scooter, 5 for Shared Cars
        """  # noqa: D205
        # Fleet State

        # We calculate for each vehicle mode dedicated charging plans based on the available resources

        charging_plan = []

        # Account for the possibility that there is no charging station available (could happen in coordinated shared infrastructure, e.g.)
        if not self._operator.charging_infrastructure.get_locations():
            self.logger.info(
                "No charging stations available. No charging plan generated."
            )
            return charging_plan

        if not self._allow_queue:
            # for virtual CS, we can use the capacity, as it gets updated
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

        for vehicle in vehicles_to_charge:
            hex = vehicle.position.get_region_id()

            # Get nearest charging station (.loc -> destination, [[]] -> Origin)
            if not self._allow_queue:
                # considering only the ones with remaining capacity from other charging plans
                sorted_base_list = self._distance_matrix.loc[
                    list(capacity_to_consider.keys())
                ][[hex]].sort_values(by=hex, ascending=True)

                if sorted_base_list.empty:
                    # no charging stations available because capacity exhausted
                    self.logger.debug(
                        "Reserved capacity at all charging stations exhausted, skipping creation of charging tasks after %s tasks were created.",
                        len(charging_plan),
                    )
                    break

                # Select Nearest Base
                selected_base_distance = sorted_base_list.iat[0, 0]
                # add safety buffer when vehicle is unluckily positioned at the very edge of the hexagon
                selected_base_distance += self._base_buffer
                selected_base = sorted_base_list.index[0]
                if not vehicle.energy_system.has_enough_energy(
                    distance=selected_base_distance, use_buffer=False
                ):
                    self.logger.debug(
                        "Vehicle %s considered for charging at %s has not enough state of charge to relocate there, skipping.",
                        vehicle.uid,
                        selected_base,
                    )
                    continue
                selected_charging_station = [  # noqa: RUF015
                    x
                    for x in self._operator.charging_infrastructure.charging_stations
                    if x.location == selected_base
                ][0]
            else:
                sorted_base_list = self._distance_matrix.loc[
                    self._operator.charging_infrastructure.get_locations()
                ][[hex]].sort_values(by=hex, ascending=True)

                selected_base = None
                selected_base_distance = None
                selected_charging_station = None
                if vehicle.is_electric:
                    # we prioritize based on the queue
                    # TODO: priorize based on CS.current_queue_time
                    for queue in [0, 2, 5, 10]:
                        for index_base, row_base in sorted_base_list.iterrows():
                            selected_base = index_base
                            available_charging_stations = [
                                x
                                for x in self._operator.charging_infrastructure.charging_stations
                                if len(x.plugs.queue) <= queue
                            ]
                            if len(available_charging_stations) > 0:
                                selected_charging_station = [
                                    x
                                    for x in available_charging_stations
                                    if x.location == selected_base
                                ]
                                if len(selected_charging_station) > 0:
                                    selected_charging_station = (
                                        selected_charging_station[0]
                                    )
                                    selected_base_distance = row_base[hex]
                                    selected_base_distance += self._base_buffer
                                    break
                        else:
                            # if we broke out the inner loop, we did so, because we found a charging station
                            # only if that's not the case we need to continue with the outer loop looking for longer queue ones
                            continue
                        break

                    # sometimes the queue is too long and we have to disregard it
                    if selected_base_distance is None:
                        for index_base, row_base in sorted_base_list.iterrows():
                            selected_base = index_base
                            available_charging_stations = [
                                x
                                for x in self._operator.charging_infrastructure.charging_stations
                            ]
                            if len(available_charging_stations) > 0:
                                selected_charging_station = [
                                    x
                                    for x in available_charging_stations
                                    if x.location == selected_base
                                ]
                                if len(selected_charging_station) > 0:
                                    selected_charging_station = (
                                        selected_charging_station[0]
                                    )
                                    selected_base_distance = row_base[hex]
                                    selected_base_distance += self._base_buffer
                                    break

                    if (
                        selected_base_distance is None
                        or selected_charging_station is None
                        or selected_base is None
                    ):
                        self.logger.debug(
                            "No charging station found for vehicle %s in queue mode, skipping.",
                            vehicle.uid,
                        )
                        continue

                    if not vehicle.energy_system.has_enough_energy(
                        distance=selected_base_distance, use_buffer=False
                    ):
                        self.logger.debug(
                            "Vehicle %s considered for charging at %s has not enough state of charge to relocate there, skipping.",
                            vehicle.uid,
                            selected_charging_station,
                        )
                        continue

                if not vehicle.is_electric:
                    for index_base, row_base in sorted_base_list.iterrows():
                        selected_base = index_base
                        available_charging_stations = [
                            x
                            for x in self._operator.charging_infrastructure.charging_stations
                        ]
                        if len(available_charging_stations) > 0:
                            selected_charging_station = [  # noqa: RUF015
                                x
                                for x in available_charging_stations
                                if x.location == selected_base
                            ][0]
                            selected_base_distance = row_base[hex]
                            break
                    # How many vehicles can we move to the base and charge?
                    if (
                        selected_base_distance is None
                        or selected_charging_station is None
                        or selected_base is None
                    ):
                        self.logger.debug(
                            "No charging station found for non-electric vehicle %s, skipping.",
                            vehicle.uid,
                        )
                        continue

            pick_up_vehicles = 1

            # Collection of Charging Tasks per Service Worker
            charging_entries = []

            # Charging Task from current region to fleet base
            charging_entry = (
                hex,
                selected_base,
                pick_up_vehicles,
                selected_base_distance,
                selected_charging_station,
                vehicle,
            )

            if not self._allow_queue:
                capacity_to_consider[selected_base] -= pick_up_vehicles
                if capacity_to_consider[selected_base] == 0:
                    del capacity_to_consider[selected_base]

            # Add main chargin task to charging tasks
            if pick_up_vehicles > 0:
                charging_entries.append(charging_entry)

            # Store Charging Task
            if len(charging_entries) > 0:
                charging_plan.append(charging_entries)
            # Save Charging Plan of Vehicle Mode

        return charging_plan

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
