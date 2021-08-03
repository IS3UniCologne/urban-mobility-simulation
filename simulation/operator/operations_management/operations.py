import queue
from collections import deque

from simulation.operator.operations_management.service_tasks.charging_task import ChargingTask
from simulation.operator.operations_management.service_tasks.multi_service_task import MultiServiceTask
from simulation.operator.operations_management.service_worker import ServiceWorker, ServiceWorkerState


class Operations:

    def __init__(self, env, vehicle_fleet, no_service_workers, time_between_operations,
                 relocation_scheduler, payment_engine, available_modes, available_modes_supply,
                 state_of_charge_threshold):
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

        # Init Service Workers
        self._service_workers = []
        self.add_service_workers(no_service_workers)

    def add_service_workers(self, number_of_service_workers):
        for i in range(number_of_service_workers):
            self._service_workers.append(ServiceWorker(self._env))

    @property
    def free_service_workers(self):
        free_service_workers = filter(lambda service_worker: service_worker.state == ServiceWorkerState.FREE, self._service_workers)
        return list(free_service_workers)

    def run_operations(self):
        while True:
            # Operations begin after first day
            yield self._env.timeout(self._time_between_operations)

            # Retrieve Vehicle Transactions
            transactions = self._payment_engine.get_transactions()

            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans, used_capacity = self._relocation_scheduler.generate_charging_plan(transactions)

            # Generate Charging Tasks from Chargings Plans
            charging_tasks = deque()

            for mode in self._available_modes:
                charging_plans_for_current_mode = charging_plans[mode]

                for charging_plan in charging_plans_for_current_mode:
                    if len(charging_plan) > 1:
                        multi_service_task = MultiServiceTask()
                        # Pooled Task
                        for task in charging_plan:
                            origin, destination, no_vehicle_to_charge, distance_to_base = task

                            charging_task = ChargingTask(origin, destination, no_vehicle_to_charge, mode, distance_to_base,
                                         self._vehicle_fleet, self._state_of_charge_threshold)

                            multi_service_task.append_task(charging_task)

                        charging_tasks.append(multi_service_task)
                    else:
                        # Single Task
                        origin, destination, no_vehicle_to_charge, distance_to_base = charging_plan[0]

                        charging_task = ChargingTask(origin, destination, no_vehicle_to_charge, mode, distance_to_base,
                                                     self._vehicle_fleet, self._state_of_charge_threshold)
                        charging_tasks.append(charging_task)

            # Assign Service Workers to Charging Tasks
            for service_worker in self.free_service_workers:
                if len(charging_tasks)> 0:
                    next_charging_task = charging_tasks.popleft()
                    self._env.process(service_worker.execute_task(next_charging_task))

            # Use Remaining Service Workers for Relocation Tasks

            # After Charging Tasks are done, use service workers for remaining relocation tasks