from simulation.operator.operations_management.service_tasks.charging_task import ChargingTask
from simulation.operator.operations_management.service_tasks.multi_service_task import MultiServiceTask

import logging

class Operations:

    def __init__(self, env, vehicle_fleet, no_service_workers, time_between_operations,
                 relocation_scheduler, payment_engine, available_modes, available_modes_supply,
                 state_of_charge_threshold, task_queue):
        """

        :param env: SimPy Environment
        :param relocation_scheduler: Calculates Relocation and Charging Plans (centralizied and currently rule based)
        :param vehicle_fleet: The underlying vehicle fleet to operate
        :param service_workers: list of service workers
        :param time_between_operations: Delay in min between operations (e.g., 1440 (min) => every 24 hours
        :param payment_engine: Handles all transactions
        :param available_modes: List of available vehicle modes
        :param available_modes_supply: List of number of available vehicles per mode (aligned with available_modes)
        :param state_of_charge_threshold: State of Charge Percent; below that => vehicle needs charging

        """

        self._env = env
        self._vehicle_fleet = vehicle_fleet
        self._no_service_workers = no_service_workers
        self._time_between_operations = time_between_operations

        self._relocation_scheduler = relocation_scheduler

        # To access vehicle transactions
        self._payment_engine = payment_engine
        self._available_modes = available_modes # Modes in Fleet
        self._available_modes_supply = available_modes_supply # Number of Vehicles in Fleet per Mode e.g., [100, 100, 50]

        self._state_of_charge_threshold = state_of_charge_threshold

        # Task List
        self._task_queue = task_queue
        self._scheduled_tasks = []

        # Events
        self._charging_plan_updated = env.event()

    @property
    def charging_plan_updated(self):
        return self._charging_plan_updated

    def run_operations(self):
        while True:
            # Operations begin after first day
            yield self._env.timeout(self._time_between_operations)

            # Retrieve Vehicle Transactions
            transactions = self._payment_engine.get_transactions()

            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans, used_capacity = self._relocation_scheduler.generate_charging_plan(transactions)

            # We track the charging events
            charging_events = []

            for mode in self._available_modes:
                charging_plans_for_current_mode = charging_plans[mode]

                for charging_plan in charging_plans_for_current_mode:
                    if len(charging_plan) > 1:
                        multi_service_task = MultiServiceTask(self._env)
                        # Pooled Task
                        for task in charging_plan:
                            origin, destination, no_vehicle_to_charge, distance_to_base = task

                            charging_task = ChargingTask(self._env, origin, destination, no_vehicle_to_charge, mode, distance_to_base,
                                         self._vehicle_fleet, self._state_of_charge_threshold)

                            multi_service_task.append_task(charging_task)

                        # Schedule to Queue
                        self._scheduled_tasks.append(multi_service_task)

                        # Remember event for multi service tasks
                        charging_events.append(multi_service_task.task_finished)
                    else:
                        # Single Task
                        origin, destination, no_vehicle_to_charge, distance_to_base = charging_plan[0]

                        charging_task = ChargingTask(self._env, origin, destination, no_vehicle_to_charge, mode, distance_to_base,
                                                     self._vehicle_fleet, self._state_of_charge_threshold)

                        # Schedule to Queue
                        self._scheduled_tasks.append(charging_task)

                        # Remember event for multi service tasks
                        charging_events.append(charging_task.task_finished)

            # Insert Tasks into Task Queue
            self._task_queue.bulk_append(self._scheduled_tasks)

            logging.info(f"Charging Tasks scheduled. In total {len(charging_events)} charging tasks are generated.",
                extra={"clazz": self.__class__.__name__, "oid": ""})

            # Notify listeners
            self._charging_plan_updated.succeed()
            self._charging_plan_updated = self._env.event()

            # Use Remaining Service Workers for Relocation Tasks
            # TODO:
            # Wait until all charging events are processed
            yield self._env.all_of(charging_events)

            logging.info(f"All Charging Tasks have been fulfilled. Re-Generating Relocation Plan.",
                extra={"clazz": self.__class__.__name__, "oid": ""})

            # Update Relocation Tasks based on newly available vehicles (after charging)
            # TODO: Clean Tasks list

