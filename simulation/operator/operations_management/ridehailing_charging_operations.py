import logging

from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.service_tasks.charging_task_ridehailing import (
    ChargingTaskRidehailing,
)
from simulation.operator.operations_management.task_queue import TaskQueue


class RideHailingChargingOperations(OperationsInterface):
    # TODO: refactor base_regions and capacity, such that it relates to the infrastructure of the operator. This also implies that we need to register the infrastructure after the opeartor is initialised

    def __init__(
        self,
        env,
        distance_matrix,
        time_between_operations,
        operation_duration,
        available_modes,
        available_modes_supply,
        state_of_charge_threshold,
    ):
        super(RideHailingChargingOperations, self).__init__(env=env)

        # Distance Matrix between Regions
        self._distance_matrix = distance_matrix

        # To access vehicle transactions
        self._available_modes = available_modes  # Modes in Fleet
        self._available_modes_supply = available_modes_supply  # Number of Vehicles in Fleet per Mode e.g., [100, 100, 50]

        self._state_of_charge_threshold = state_of_charge_threshold

        # Task List
        self._task_queue = TaskQueue(env)
        self._scheduled_tasks = []

        # Events
        self._charging_plan_updated = env.event()
        self._operations_started = env.event()

        # When to start operations (every 1440 min)
        self._time_between_operations = time_between_operations

        # Shift Duration (OM shift duration)
        self._duration_of_operations = operation_duration  # mins
        self._counter = 0

    @property
    def charging_plan_updated(self):
        return self._charging_plan_updated

    def execute(self):
        "Below, we combine the old operational logic from operations_ridehailing.py and rebalancing_scheduler_ridehailing.py"

        while True:
            # Operations begin after first day
            self._scheduled_tasks = []
            yield self._env.timeout(self._time_between_operations)

            # Retrieve Vehicle Transactions
            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans = self.generate_charging_plan()

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
                    self._operator_reference.fleet,
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
                f"There are {self._operator_reference.fleet.get_all_vehicles_below_soc_level(self._state_of_charge_threshold)} vehicles with low state of charge.",
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
            logging.warning(
                "No charging stations available. No charging plan generated.",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            return charging_plan

        for vehicle in vehicles_to_charge:
            hex = vehicle.position.get_hexagon(return_geom=False)[0]

            # Get nearest charging station (.loc -> destination, [[]] -> Origin)
            sorted_base_list = self._distance_matrix.loc[
                self._operator_reference.charging_infrastructure.get_locations()
            ][[hex]].sort_values(by=hex, ascending=True)

            selected_base_distance = None
            # Select Nearest Base
            if vehicle.is_electric:
                # we prioritize based on the queue
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
                                selected_charging_station = selected_charging_station[0]
                                selected_base_distance = row_base[hex]
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
                                selected_charging_station = selected_charging_station[0]
                                selected_base_distance = row_base[hex]
                                break

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

        for mode in self._available_modes:
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
