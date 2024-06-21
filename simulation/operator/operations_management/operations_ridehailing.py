import logging

from simulation.operator.operations_management.service_tasks.charging_task_ridehailing import (
    ChargingTaskRidehailing,
)


# TODO: refactor to adhere to base class "Operator"
class OperationsRidehailing:
    def __init__(
        self,
        env,
        vehicle_fleet,
        time_between_operations,
        operation_duration,
        relocation_scheduler,
        payment_engine,
        available_modes,
        available_modes_supply,
        state_of_charge_threshold,
        task_queue,
        charging_stations,
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

        self._relocation_scheduler = relocation_scheduler

        # To access vehicle transactions
        self._payment_engine = payment_engine
        self._available_modes = available_modes  # Modes in Fleet
        self._available_modes_supply = available_modes_supply  # Number of Vehicles in Fleet per Mode e.g., [100, 100, 50]

        self._state_of_charge_threshold = state_of_charge_threshold

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
        self._charging_stations = charging_stations
        self._counter = 0

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
            self._scheduled_tasks = []
            yield self._operations_started

            # Retrieve Vehicle Transactions
            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans = self._relocation_scheduler.generate_charging_plan(
                self._charging_stations
            )

            # We track the charging events
            charging_events = []

            # No Vehicles to be charged
            no_vehicles_scheduled_to_charge = {}

            for charging_plan in charging_plans:
                (
                    origin,
                    destination,
                    no_vehicle_to_charge,
                    distance_to_base,
                    charging_station,
                    vehicle,
                ) = charging_plan[0]

                charging_task = ChargingTaskRidehailing(
                    self._env,
                    origin,
                    destination,
                    no_vehicle_to_charge,
                    distance_to_base,
                    self._vehicle_fleet,
                    self._state_of_charge_threshold,
                    charging_station,
                    vehicle,
                )

                # Schedule to Queue
                self._scheduled_tasks.append(charging_task)
                # Remember event for multi service tasks
                charging_events.append(charging_task.task_finished)

                # Count Vehicles to be charged
                # no_vehicles_scheduled_to_charge['a'] += no_vehicle_to_charge
            # Insert Tasks into Task Queue
            self._task_queue.bulk_append(self._scheduled_tasks)

            logging.debug(
                f"There are {self._vehicle_fleet.get_all_vehicles_below_soc_level(self._state_of_charge_threshold)} vehicles with low state of charge.",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

            logging.debug(
                f"Charging Tasks scheduled. In total {len(charging_events)} charging tasks are generated. Count: {no_vehicles_scheduled_to_charge}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            # Notify listeners
            self._charging_plan_updated.succeed()
            self._charging_plan_updated = self._env.event()
            while self._task_queue.count > 0:
                next_task = self._task_queue.popleft()
                logging.debug(
                    f"Processing following task: {next_task}.",
                    extra={"clazz": self.__class__.__name__},
                )
                # TODO: we do not need a service ID here
                self._env.process(next_task.execute(0))
                self._counter += 1

            # ### TODO: activate relocation for ridehailing later
