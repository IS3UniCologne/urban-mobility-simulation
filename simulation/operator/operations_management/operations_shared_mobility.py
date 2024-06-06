import logging

from simulation.operator.operations_management.service_tasks.charging_task import (
    ChargingTask,
)
from simulation.operator.operations_management.service_tasks.multi_service_task import (
    MultiServiceTask,
)
from simulation.operator.operations_management.service_tasks.relocation_task import (
    RelocationTask,
)


# TODO: refactor to adhere to base class "Operator"
class Operations:
    def __init__(
        self,
        env,
        vehicle_fleet,
        no_service_workers,
        time_between_operations,
        operation_duration,
        relocation_scheduler,
        payment_engine,
        available_modes,
        available_modes_supply,
        state_of_charge_threshold,
        task_queue,
    ):
        """

        :param env: SimPy Environment
        :param relocation_scheduler: Calculates Relocation and Charging Plans (centralizied and currently rule based)
        :param vehicle_fleet: The underlying vehicle fleet to operate
        :param service_workers: list of service workers
        :param time_between_operations: Delay in min between operations (e.g., 1440 (min) => every 24 hours
        :param operation_duration: Operation Time (Shift of Service Workers)
        :param payment_engine: Handles all transactions
        :param available_modes: List of available vehicle modes
        :param available_modes_supply: List of number of available vehicles per mode (aligned with available_modes)
        :param state_of_charge_threshold: State of Charge Percent; below that => vehicle needs charging

        """

        self._env = env
        self._vehicle_fleet = vehicle_fleet
        self._no_service_workers = no_service_workers

        self._relocation_scheduler = relocation_scheduler

        # To access vehicle transactions
        self._payment_engine = payment_engine
        self._available_modes = available_modes  # Modes in Fleet
        self._available_modes_supply = available_modes_supply  # Number of Vehicles in Fleet per Mode e.g., [100, 100, 50]

        self._state_of_charge_threshold = state_of_charge_threshold  # > strategy

        # Task List
        self._task_queue = task_queue
        self._scheduled_tasks = []

        # Events
        self._charging_plan_updated = env.event()
        self._operations_started = env.event()

        # When to start operations (every 1440 min)
        self._time_between_operations = time_between_operations

        # Shift Duration (OM shift duration)
        self._duration_of_operations = operation_duration  # mins

    @property
    def charging_plan_updated(self):
        return self._charging_plan_updated

    def timer(self):
        while True:
            yield self._env.timeout(self._time_between_operations)
            self._operations_started.succeed()
            self._operations_started = self._env.event()
            logging.warning(
                "Operations started.",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

    def run_operations(self):
        while True:
            # Operations begin after first day
            yield self._operations_started

            # Clean old jobs (if there are some left)
            self._task_queue.clear()

            # Retrieve Vehicle Transactions
            transactions = self._payment_engine.get_transactions()

            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            (charging_plans, used_capacity) = (
                self._relocation_scheduler.generate_charging_plan(transactions)
            )

            # We track the charging events
            charging_events = []

            # No Vehicles to be charged
            no_vehicles_scheduled_to_charge = {}

            for mode in self._available_modes:
                charging_plans_for_current_mode = charging_plans[mode]

                # Set Counter to 0
                if mode not in no_vehicles_scheduled_to_charge:
                    no_vehicles_scheduled_to_charge[mode] = 0

                for charging_plan in charging_plans_for_current_mode:
                    if len(charging_plan) > 1:
                        multi_service_task = MultiServiceTask(self._env)
                        # Pooled Task
                        for task in charging_plan:
                            (
                                origin,
                                destination,
                                no_vehicle_to_charge,
                                distance_to_base,
                            ) = task

                            charging_task = ChargingTask(
                                self._env,
                                origin,
                                destination,
                                no_vehicle_to_charge,
                                mode,
                                distance_to_base,
                                self._vehicle_fleet,
                                self._state_of_charge_threshold,
                            )

                            multi_service_task.append_task(charging_task)

                            # Count Vehicles to be charged
                            no_vehicles_scheduled_to_charge[mode] += (
                                no_vehicle_to_charge
                            )

                        # Schedule to Queue
                        self._scheduled_tasks.append(multi_service_task)

                        # Remember event for multi service tasks
                        charging_events.append(multi_service_task.task_finished)
                    else:
                        # Single Task
                        (
                            origin,
                            destination,
                            no_vehicle_to_charge,
                            distance_to_base,
                        ) = charging_plan[0]

                        charging_task = ChargingTask(
                            self._env,
                            origin,
                            destination,
                            no_vehicle_to_charge,
                            mode,
                            distance_to_base,
                            self._vehicle_fleet,
                            self._state_of_charge_threshold,
                        )

                        # Schedule to Queue
                        self._scheduled_tasks.append(charging_task)

                        # Remember event for multi service tasks
                        charging_events.append(charging_task.task_finished)

                        # Count Vehicles to be charged
                        no_vehicles_scheduled_to_charge[mode] += no_vehicle_to_charge

            # Insert Tasks into Task Queue
            self._task_queue.bulk_append(self._scheduled_tasks)

            logging.info(
                f"There are {self._vehicle_fleet.get_all_vehicles_below_soc_level(self._state_of_charge_threshold)} vehicles with low state of charge.",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

            logging.info(
                f"Charging Tasks scheduled. In total {len(charging_events)} charging tasks are generated. Count: {no_vehicles_scheduled_to_charge}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

            # Notify listeners
            self._charging_plan_updated.succeed()
            self._charging_plan_updated = self._env.event()

            # While Shift is not over, recalculate relocation plans and execute them.
            while (
                self._env.now % self._time_between_operations
                < self._duration_of_operations
            ):
                logging.info(
                    "Planning next relocation schedule.",
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )

                # Reset Scheduled Tasks
                self._scheduled_tasks.clear()

                # Wait 2 Minutes, then (re-)schedule relocation
                yield self._env.timeout(2)

                transactions = self._payment_engine.get_transactions()

                relocations = self._relocation_scheduler.generate_relocation_plan(
                    transactions
                )

                # We track the charging events
                relocation_events = []

                # No Vehicles to be charged
                no_vehicles_scheduled_to_relocate = {}

                for mode in self._available_modes:
                    relocation_plans_for_current_mode = relocations[mode]

                    # Set Counter to 0
                    if mode not in no_vehicles_scheduled_to_relocate:
                        no_vehicles_scheduled_to_relocate[mode] = 0

                    for relocation_plan in relocation_plans_for_current_mode:
                        if len(relocation_plan) > 1:
                            multi_service_task = MultiServiceTask(self._env)
                            # Pooled Task
                            for task in relocation_plan:
                                (
                                    origin,
                                    destination,
                                    no_vehicle_to_relocate,
                                    relocation_distance,
                                ) = task

                                relocation_task = RelocationTask(
                                    self._env,
                                    origin,
                                    destination,
                                    no_vehicle_to_relocate,
                                    relocation_distance,
                                    mode,
                                    self._vehicle_fleet,
                                )

                                multi_service_task.append_task(relocation_task)

                                # Count Vehicles to be charged
                                no_vehicles_scheduled_to_relocate[mode] += (
                                    no_vehicle_to_relocate
                                )

                            # Schedule to Queue
                            self._scheduled_tasks.append(multi_service_task)

                            # Remember event for multi service tasks
                            relocation_events.append(multi_service_task.task_finished)
                        else:
                            # Single Task
                            (
                                origin,
                                destination,
                                no_vehicle_to_relocate,
                                relocation_distance,
                            ) = relocation_plan[0]

                            relocation_task = RelocationTask(
                                self._env,
                                origin,
                                destination,
                                no_vehicle_to_relocate,
                                relocation_distance,
                                mode,
                                self._vehicle_fleet,
                            )

                            # Schedule to Queue
                            self._scheduled_tasks.append(relocation_task)

                            # Remember event for multi service tasks
                            relocation_events.append(relocation_task.task_finished)

                            # Count Vehicles to be charged
                            no_vehicles_scheduled_to_relocate[mode] += (
                                no_vehicle_to_relocate
                            )

                # Insert Tasks into Task Queue
                self._task_queue.bulk_append(self._scheduled_tasks)

                if len(charging_events):
                    # Wait for Charging events
                    yield self._env.all_of(charging_events)

                    logging.info(
                        "All Charging Tasks have been fulfilled. Re-Generating Relocation Plan.",
                        extra={"clazz": self.__class__.__name__, "oid": ""},
                    )

                # Wait for relocation events to be processed
                yield self._env.all_of(relocation_events)

                logging.info(
                    "Planned Relocation Tasks have been fulfilled. Re-Generating Relocation Plan.",
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )
