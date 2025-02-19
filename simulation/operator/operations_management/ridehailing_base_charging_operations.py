import logging

import h3
import pandas as pd
from beartype.door import is_bearable
from simpy import AnyOf

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.service_tasks.charging_task_ridehailing import (
    ChargingTaskRidehailing,
)
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.world.world import World


class RideHailingBaseChargingOperations(OperationsInterface):
    def __init__(
        self,
        env,
        distance_matrix,
        time_between_operations,
        operation_duration,
        available_modes,
        available_modes_supply,
        state_of_charge_threshold,
        allow_queue,
    ):
        super(RideHailingBaseChargingOperations, self).__init__(env=env)

        self._world = None  # defer
        self._config = Configuration.instance()

        # Distance Matrix between Regions
        self._distance_matrix = distance_matrix
        self._base_buffer = h3.edge_length(
            self._config.spatial_resolution_value - 1, unit="m"
        )  # use a buffer when calculating distances to charging stations of next coarser grid level edge length (radius)

        # To access vehicle transactions
        self._available_modes = available_modes  # Modes in Fleet
        self._available_modes_supply = available_modes_supply  # Number of Vehicles in Fleet per Mode e.g., [100, 100, 50]

        self._state_of_charge_threshold = state_of_charge_threshold
        self._allow_queue = allow_queue

        # Task List
        self._task_queue = TaskQueue(env)
        self._scheduled_tasks = []

        self._task_transactions = []

        # Events
        self._charging_plan_updated = env.event()
        self._operations_started = env.event()
        self._task_executed = env.event()

        # When to start operations
        self._time_between_operations = time_between_operations

        # Shift Duration
        self._duration_of_operations = operation_duration  # mins

    @property
    def charging_plan_updated(self):
        return self._charging_plan_updated

    @property
    def task_executed(self):
        return self._task_executed

    def execute(self):
        self._world = World.instance()

        "Below, we combine the old operational logic from operations_ridehailing.py and rebalancing_scheduler_ridehailing.py"

        while True:
            # Operations begin after first day
            self._scheduled_tasks = []
            yield self._env.timeout(self._time_between_operations)

            # Retrieve Vehicle Transactions
            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans = self.generate_charging_plan()

            if not charging_plans:
                continue

            for charging_plan in charging_plans:
                (
                    origin,
                    destination,
                    no_vehicle_to_charge,
                    distance_to_base,
                    charging_station,
                    vehicle,
                ) = charging_plan[0]

                # we need to do some differentiation here, because we need to check if the charging station is virtual, and if it is, we need to check if we are in a context with reserved timeslots
                scheduled_time = None
                if is_bearable(charging_station, VirtualChargingStation):
                    scheduled_time = charging_station.valid_timeframe
                    try:
                        scheduled_time = scheduled_time[0]
                    except TypeError:
                        # 'NoneType' object is not subscriptable > not using reservation timeslots
                        scheduled_time = None

                charging_task = ChargingTaskRidehailing(
                    self._env,
                    origin,
                    destination,
                    no_vehicle_to_charge,
                    distance_to_base,
                    self._state_of_charge_threshold,
                    charging_station,
                    vehicle,
                    scheduled_time=scheduled_time,
                )

                # Schedule to Queue
                self._scheduled_tasks.append(charging_task)
                # update virtual charging infrastructure
                # if is_bearable(
                #     self._operator_reference.charging_infrastructure,
                #     VirtualChargingInfrastructure,
                # ):
                #     charging_station.update_capacity(
                #         charging_station.capacity - 1, charging_station.valid_timeframe
                #     )

                # Track task completion
                self._env.process(self._track_task(charging_task))

                # Count Vehicles to be charged
                # no_vehicles_scheduled_to_charge['a'] += no_vehicle_to_charge
            # Insert Tasks into Task Queue
            self._task_queue.bulk_append(self._scheduled_tasks)

            logging.info(
                f"There are {self._operator_reference.fleet.count_vehicles_below_soc_level(self._state_of_charge_threshold)} vehicles with low state of charge.",
                extra={
                    "clazz": self.__class__.__name__,
                    "oid": self._operator_reference.id,
                },
            )

            logging.info(
                f"Charging Tasks scheduled. In total {len(charging_plans)} charging tasks are generated.",
                extra={
                    "clazz": self.__class__.__name__,
                    "oid": self._operator_reference.id,
                },
            )
            # Notify listeners
            self._charging_plan_updated.succeed()
            self._charging_plan_updated = self._env.event()

            while self._task_queue.count > 0:
                next_task = self._task_queue.popleft()
                logging.debug(
                    f"Processing following task: {next_task}.",
                    extra={
                        "clazz": self.__class__.__name__,
                        "oid": self._operator_reference.id,
                    },
                )
                self._env.process(next_task.execute())
                self._task_executed.succeed(next_task)
                self._task_executed = self._env.event()

            # ### TODO: activate relocation for ridehailing later

    def generate_charging_plan(self):
        """
        Generate a rule based charging plan based on given service worker capacity
        :return: **charging_plan**: Dictionary with keys for vehicle modes and values with lists of multiple
                charging tasks
                **used_capacity**: How many service workers are planned to cope with charging needs
        """
        # Get Current Fleet State
        vehicles_to_charge = self._operator_reference.fleet.mark_vehicles_to_be_charged(
            self._state_of_charge_threshold
        )
        # if config.store_results:
        #     state.to_csv(Path(config.output_path, config.fleet_state_file), index = False)

        charging_plans = self.calculate_charging_plan(vehicles_to_charge)

        return charging_plans

    def calculate_charging_plan(self, vehicles_to_charge):
        """
        :param vehicles_to_charge: List of vehicles to be charged
        :return: all_charging_plans and used capacity per mode
                all_charging_plans {"SharedKickScooter":[[(origin, destination, number of vehicles to pick up, destination to base), ()], [()],
                                    "SharedScooter": [], "SharedCar":[]}
                used_capacity = [1, 3, 5] => per available vehicle mode returns number of service workers assigned to charge these vehicles
                                          => 1 SW for Kick Scooter, 3 for Shared Scooter, 5 for Shared Cars
        """

        # Fleet State

        # We calculate for each vehicle mode dedicated charging plans based on the available resources

        charging_plan = []

        # Account for the possibility that there is no charging station available (could happen in coordinated shared infrastructure, e.g.)
        if not self._operator_reference.charging_infrastructure.get_locations():
            logging.info(
                "No charging stations available. No charging plan generated.",
                extra={
                    "clazz": self.__class__.__name__,
                    "oid": self._operator_reference.id,
                },
            )
            return charging_plan

        if not self._allow_queue:
            # for virtual CS, we can use the capacity, as it gets updated
            if is_bearable(
                self._operator_reference.charging_infrastructure,
                VirtualChargingInfrastructure,
            ):
                capacity_to_consider = {
                    x.location: x.capacity
                    for x in self._operator_reference.charging_infrastructure.charging_stations
                    if x.capacity > 0
                }
            else:
                # otherwise we need to consider capacity minus current plugged in vehicles:
                capacity_to_consider = {
                    x.location: x.capacity - len(x.plugs.users)
                    for x in self._operator_reference.charging_infrastructure.charging_stations
                    if x.capacity - len(x.plugs.users) > 0
                }

        for vehicle in vehicles_to_charge:
            hex = vehicle.position.get_hexagon_id()

            # Get nearest charging station (.loc -> destination, [[]] -> Origin)
            if not self._allow_queue:
                # considering only the ones with remaining capacity from other charging plans
                sorted_base_list = self._distance_matrix.loc[
                    list(capacity_to_consider.keys())
                ][[hex]].sort_values(by=hex, ascending=True)

                if sorted_base_list.empty:
                    # no charging stations available because capacity exhausted
                    logging.debug(
                        "Reserved capacity at all charging stations exhausted, skipping creation of charging tasks after %s tasks were created.",
                        len(charging_plan),
                        extra={
                            "clazz": self.__class__.__name__,
                            "oid": self._operator_reference.id,
                        },
                    )
                    break

                # Select Nearest Base
                selected_base_distance = sorted_base_list.iat[0, 0]
                # add safety buffer when vehicle is unluckily positioned at the very edge of the hexagon
                selected_base_distance += self._base_buffer
                selected_base = sorted_base_list.index[0]
                if not vehicle.has_enough_state_of_charge(
                    selected_base_distance, consider_buffer=False
                ):
                    logging.debug(
                        f"Vehicle {vehicle.id} considered for charging at {selected_base} has not enough state of charge to relocate there, skipping.",
                        extra={
                            "clazz": self.__class__.__name__,
                            "oid": self._operator_reference.id,
                        },
                    )
                    continue
                selected_charging_station = [
                    x
                    for x in self._operator_reference.charging_infrastructure.charging_stations
                    if x.location == selected_base
                ][0]
            else:
                sorted_base_list = self._distance_matrix.loc[
                    self._operator_reference.charging_infrastructure.get_locations()
                ][[hex]].sort_values(by=hex, ascending=True)

                selected_base_distance = None
                if vehicle.is_electric:
                    # we prioritize based on the queue
                    # TODO: priorize based on CS.current_queue_time
                    for queue in [0, 2, 5, 10]:
                        for index_base, row_base in sorted_base_list.iterrows():
                            selected_base = index_base
                            available_charging_stations = [
                                x
                                for x in self._operator_reference.charging_infrastructure.charging_stations
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
                    if not selected_base_distance:
                        for index_base, row_base in sorted_base_list.iterrows():
                            selected_base = index_base
                            available_charging_stations = [
                                x
                                for x in self._operator_reference.charging_infrastructure.charging_stations
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

                    if not vehicle.has_enough_state_of_charge(
                        selected_base_distance, consider_buffer=False
                    ):
                        logging.debug(
                            f"Vehicle {vehicle.id} considered for charging at {selected_charging_station} has not enough state of charge to relocate there, skipping.",
                            extra={
                                "clazz": self.__class__.__name__,
                                "oid": self._operator_reference.id,
                            },
                        )
                        continue

                if not vehicle.is_electric:
                    for index_base, row_base in sorted_base_list.iterrows():
                        selected_base = index_base
                        available_charging_stations = [
                            x
                            for x in self._operator_reference.charging_infrastructure.charging_stations
                        ]
                        if len(available_charging_stations) > 0:
                            selected_charging_station = [
                                x
                                for x in available_charging_stations
                                if x.location == selected_base
                            ][0]
                            selected_base_distance = row_base[hex]
                            break

            # How many vehicles can we move to the base and charge?
            pick_up_vehicles = 1

            # Collection of Charging Tasks per Service Worker
            chargings_tasks = []

            # Charging Task from current region to fleet base
            charging_task = (
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
                chargings_tasks.append(charging_task)

            # Store Charging Task
            if len(chargings_tasks) > 0:
                charging_plan.append(chargings_tasks)

            # Save Charging Plan of Vehicle Mode

        return charging_plan

    def get_max_capacity_per_unit(self, mode):
        # Mode Specific Collection Capacity per Service Worker (i.e., how many vehicles can one sw collect)
        if mode == "RideHailingCar":
            max_capacity_per_unit = 1
        elif mode == "AutonomousCar":
            max_capacity_per_unit = 1
        else:
            raise NotImplementedError("Not Implemented")
        return max_capacity_per_unit

    def _track_task(self, task):
        yield AnyOf(self._env, [task.task_finished, self._world.simulation_finished])

        self._task_transactions.append(
            {
                "start_time": task._start_time,
                "estimated_arrival_time": task._estimated_arrival_time,
                "scheduled_time": task._scheduled_time,
                "end_time": self._env.now,
                "vehicle": task._vehicle.id,
                "state": task.state,
                "fleet": task._vehicle.fleet.id,
                "charging_station": task._charging_station.location,
                "waiting_time": task.waiting_time,
                "charging_duration": task.charging_duration,
                "estimated_completion_time": task._estimated_completion_time,
                "kWh_charged": task.kWh_charged,
            }
        )

    @property
    def task_transactions(self):
        return pd.DataFrame(self._task_transactions)
