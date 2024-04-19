import logging

from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.service_tasks.charging_task_ridehailing import (
    ChargingTaskRidehailing,
)


class RideHailingChargingOperations(OperationsInterface):
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
        super(RideHailingChargingOperations, self).__init__(env=env)

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

    def generate_charging_plan(self, charging_stations):
        """
        Generate a rule based charging plan based on given service worker capacity
        :param transactions: Simulation Transactions to calculate Fleet State and Expected In/Outlflows
        :return: **charging_plan**: Dictionary with keys for vehicle modes and values with lists of multiple
                charging tasks
                **used_capacity**: How many service workers are planned to cope with charging needs
        """
        # Get Current Fleet State
        # state = self.calculate_residual_supply(self._fleet, transactions)
        vehicles_to_charge = self.calculate_low_soc_vehicles(self._fleet)
        # if config.store_results:
        #     state.to_csv(Path(config.output_path, config.fleet_state_file), index = False)

        charging_plans = self.calculate_charging_plan(
            vehicles_to_charge, charging_stations
        )

        return charging_plans

    def calculate_charging_plan(self, vehicles_to_charge, charging_stations):
        """
        :param fleet_state: Represent current fleet state (output from function calculate_residual_supply)
        :param distance_matrix: Distance between Regions
        :param number_of_service_units: Number of  Available Service Workers
        :param available_vehicle_modes: List of available vehicle modes
        :param max_vehicle_supply: List of number of available vehicle most (supply per mode)
        :param base_regions: Possible Fleet Base Regions for charging
               (can handle multiple bases e.g.,  base_regions = ['871f1d488ffffff','871f18b21ffffff'])
               default: '871f1d488ffffff' == Berlin Mitte (Unter den Linden, Deutscher Bundestag)
        :param base_capacity: Set base capacity to 1000 vehicles (i.e., can charge that many vehicles)
        :return: all_charging_plans and used capacity per mode
                all_charging_plans {"SharedKickScooter":[[(origin, destination, number of vehicles to pick up, destination to base), ()], [()],
                                    "SharedScooter": [], "SharedCar":[]}
                used_capacity = [1, 3, 5] => per available vehicle mode returns number of service workers assigned to charge these vehicles
                                          => 1 SW for Kick Scooter, 3 for Shared Scooter, 5 for Shared Cars
        """

        # Fleet State

        # We calculate for each vehicle mode dedicated charging plans based on the available resources

        charging_plan = []

        for vehicle in vehicles_to_charge:
            hex = vehicle.position.get_default_hexagon()

            # Get nearest fleet base region (.loc -> destination, [[]] -> Origin)
            sorted_base_list = self._distance_matrix.loc[self._base_regions][
                [hex]
            ].sort_values(by=hex, ascending=True)
            selected_base_distance = None
            # Select Nearest Base
            if vehicle.electric_vehicle:
                # we prioritize based on the queue
                for queue in [0, 2, 5, 10]:
                    for index_base, row_base in sorted_base_list.iterrows():
                        selected_base = index_base
                        available_charging_stations = [
                            x for x in charging_stations if len(x.plugs.queue) <= queue
                        ]
                        if len(available_charging_stations) > 0:
                            selected_charging_station = [
                                x
                                for x in available_charging_stations
                                if x.location == selected_base
                            ]
                            if len(selected_charging_station) > 0:
                                selected_charging_station = selected_charging_station[0]
                                selected_base_distance = row_base[hex]
                                break
                # sometimes the queue is too long and we have to disregard it
                if not selected_base_distance:
                    for index_base, row_base in sorted_base_list.iterrows():
                        selected_base = index_base
                        available_charging_stations = [
                            x for x in self._charging_stations
                        ]
                        if len(available_charging_stations) > 0:
                            selected_charging_station = [
                                x
                                for x in available_charging_stations
                                if x.location == selected_base
                            ]
                            if len(selected_charging_station) > 0:
                                selected_charging_station = selected_charging_station[0]
                                selected_base_distance = row_base[hex]
                                break

            if not vehicle.electric_vehicle:
                for index_base, row_base in sorted_base_list.iterrows():
                    selected_base = index_base
                    available_charging_stations = [x for x in charging_stations]
                    if len(available_charging_stations) > 0:
                        selected_charging_station = [
                            x
                            for x in available_charging_stations
                            if x.location == selected_base
                        ][0]
                        selected_base_distance = row_base[hex]
                        break

            # Keep Track of how many vehicles are already scheduled for charging
            currently_schedules_vehicles_per_unit = 0
            logging.info(currently_schedules_vehicles_per_unit)

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

            # Add main chargin task to charging tasks
            if pick_up_vehicles > 0:
                chargings_tasks.append(charging_task)

            # Store Charging Task
            if len(chargings_tasks) > 0:
                charging_plan.append(chargings_tasks)

            # Save Charging Plan of Vehicle Mode

        return charging_plan

    def calculate_resource_capacity_split_for_charging(
        self,
        fleet_state,
        available_vehicle_modes,
        max_vehicle_supply,
        number_of_service_units,
    ):
        """
            Determine Service Worker Split Between Modes (How many workers should be assigned to charge how many vehicles)

            Process: Calculate Fraction of Low SOC Vehicles per Mode. Then calculate weighted sum.
                1. frac_i = #low_soc_vehicle_i*weight_i/max_vehicle_supply_i
                    1.1. We calculate weight as the inverse of "get_max_capacity_per_unit" for each vehicle mode
                    1.2. Thus, we ensure that not too many service workers are assigned to vehicles that can be pooled
                2. total_frac = sum frac_i
                3. Calculate how many service workers are assigned to charge vehicle mode i
                   capacity_i = frac_i/total_frac * number_of_service_units_i
        :param fleet_state: Resulting data frame from function calculate_residual_supply
        :param available_vehicle_modes: List of available vehicle modes (["SharedKickScooter", "SharedScooter", "SharedCar"]
        :param max_vehicle_supply: List of maximum number of available vehicles (order is aligned with available_vehicle_modes)
                                for example: [10, 5, 12] => 10 kick scooter, 5 scooter, 12 cars
        :param number_of_service_units: Available Service Worker Capacity
        :return: List of assigned resource workers to vehicle modes (order is aligned with available_vehicle_modes)
                        for example: Input 25 Service Workers
                                    => [5, 5, 10] <=> 5 sw for kick scooter, and scooter, 10 for cars.
        """

        current_low_soc_supply = []

        for mode in self._available_vehicle_modes:
            # Service Worker Charging Capacity per Mode
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Normalize the vehicle weight;
            # otherwise all resources are bound to kick scooters as there are way more low soc kick scooters
            # One Service Worker can "process" 40 units of kick scooters compared to 1 sw for one car.
            current_low_soc_supply.append(
                fleet_state[f"{mode}_Low_SoC"].sum() / max_capacity_per_unit
            )

        low_fraction_per_mode = [
            curr_low_supply / max_supply
            for curr_low_supply, max_supply in zip(
                current_low_soc_supply, max_vehicle_supply
            )
        ]

        # Temporary Denom
        denominator = sum(low_fraction_per_mode)

        if denominator == 0.0:
            # No Charging Needed => No Workers assigned
            return len(low_fraction_per_mode) * [0]

        # Split capacity based on the following fraction
        capacity_fraction = low_fraction_per_mode / denominator

        capacity = capacity_fraction * number_of_service_units

        capacity = [round(x) for x in capacity]

        # Rounding Fractions => Sum of Residual don't add up to available units
        # We fix this by adding or subtracting the residual to the max. element
        # Happens very rarely
        residual = number_of_service_units - sum(capacity)

        max_element = max(capacity)
        arg_max = capacity.index(max_element)

        if residual > 0:
            # We add excess supply to mode where most workforce is needed
            capacity[arg_max] += residual
        elif residual < 0:
            capacity[arg_max] = max(capacity[arg_max] + residual, 0)

        return capacity

    def get_max_capacity_per_unit(self, mode):
        # Mode Specific Collection Capacity per Service Worker (i.e., how many vehicles can one sw collect)
        if mode == "RideHailingCar":
            max_capacity_per_unit = 1
        elif mode == "AutonomousCar":
            max_capacity_per_unit = 1
        else:
            raise NotImplementedError("Not Implemented")
        return max_capacity_per_unit

    def execute(self):
        while True:
            # Operations begin after first day
            self._scheduled_tasks = []
            yield self._operations_started

            # Retrieve Vehicle Transactions
            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans = self.generate_charging_plan(self._charging_stations)

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

            logging.warning(
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
