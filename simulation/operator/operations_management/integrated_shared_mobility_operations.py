import logging
from pathlib import Path

import h3
import pandas as pd

from simulation.helper.configuration.configuration import Configuration
from simulation.helper.solvers.tsp_solver_2opt import solve_tsp
from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.service_tasks.charging_task import (
    ChargingTask,
)
from simulation.operator.operations_management.service_tasks.multi_service_task import (
    MultiServiceTask,
)
from simulation.operator.operations_management.service_tasks.relocation_task import (
    RelocationTask,
)
from simulation.operator.transactions import DemandMonitor
from simulation.operator.transactions.demand_monitor import VehicleDemandByRegion


class IntegratedSharedMobilityOperations(OperationsInterface):
    # TODO: refactor base_regions and capacity, such that it relates to the infrastructure of the operator. This also implies that we need to register the infrastructure after the opeartor is initialised
    __slots__ = (
        "_available_vehicle_modes",
        "_base_capacity",
        "_base_regions",
        "_charging_plan_updated",
        "_distance_matrix",
        "_duration_of_operations",
        "_max_vehicle_supply",
        "_operations_started",
        "_ordered_max_vehicle_supply",
        "_scheduled_tasks",
        "_state_of_charge_threshold",
        "_time_between_operations",
        "operation_duration",
    )

    def __init__(  # noqa: ANN204
        self,
        env,  # noqa: ANN001
        time_between_operations,  # noqa: ANN001
        operation_duration,  # noqa: ANN001
        distance_matrix,  # noqa: ANN001
        ordered_available_vehicle_modes,  # noqa: ANN001
        ordered_max_vehicle_supply,  # noqa: ANN001
        state_of_charge_threshold,  # noqa: ANN001
        base_regions,  # noqa: ANN001
        base_capacity,  # noqa: ANN001
    ):
        super(IntegratedSharedMobilityOperations, self).__init__(env=env)  # noqa: UP008

        # Distance Matrix between Regions
        self._distance_matrix = distance_matrix

        # List needs to be ordered such that:
        # In case of neutral demand, we count the demand for the less expensive option
        # For example: If we observe a demand for KickScooter and Scooter, we count that
        # demand to KickScooter. This ordering is defined according to the following list
        # (from left to right)
        self._available_vehicle_modes: list[str] = (
            ordered_available_vehicle_modes  # TODO: get from fleet
        )
        self._max_vehicle_supply = ordered_max_vehicle_supply  # TODO: get from fleet
        self._base_regions = base_regions
        self._base_capacity = base_capacity

        self._state_of_charge_threshold = state_of_charge_threshold

        self._scheduled_tasks = []  # TODO: move to workforce? or internal schedule?

        # Events
        self._charging_plan_updated = env.event()
        self._operations_started = env.event()

        # When to start operations (every 1440 min)
        self._time_between_operations = time_between_operations

        # Shift Duration (OM shift duration)
        self._duration_of_operations = operation_duration  # mins

    @property
    def available_vehicle_modes(self) -> list[str]:
        """Get the list of available vehicle modes.

        Returns
        -------
        list[str]
            A list of available vehicle modes.
        """
        return self._available_vehicle_modes

    def execute(self):  # noqa: ANN201
        """
        Below, we combine the old operational logic from operations.py and relocation_strategy.py
        """

        while True:
            yield self._env.timeout(self._time_between_operations)

            # Clean old jobs (if there are some left)
            self.operator._workforce.task_queue.clear()  # noqa: SLF001

            if not self.operator.transaction_log.has_successful_transaction:
                logging.debug(
                    "Skip operations, cause there has not been one successful transaction yet"
                )
                continue

            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans, used_capacity = self.generate_charging_plan()

            # We track the charging events
            charging_events = []

            # No Vehicles to be charged
            no_vehicles_scheduled_to_charge = {}

            for mode in self._available_vehicle_modes:
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
                                self._operator_reference.fleet,
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
                        origin, destination, no_vehicle_to_charge, distance_to_base = (
                            charging_plan[0]
                        )

                        charging_task = ChargingTask(
                            self._env,
                            origin,
                            destination,
                            no_vehicle_to_charge,
                            mode,
                            distance_to_base,
                            self._operator_reference.fleet,
                            self._state_of_charge_threshold,
                        )

                        # Schedule to Queue
                        self._scheduled_tasks.append(charging_task)

                        # Remember event for multi service tasks
                        charging_events.append(charging_task.task_finished)

                        # Count Vehicles to be charged
                        no_vehicles_scheduled_to_charge[mode] += no_vehicle_to_charge

            # Insert Tasks into Task Queue
            self._operator_reference._workforce.task_queue.bulk_append(  # noqa: SLF001
                self._scheduled_tasks
            )

            logging.info(
                f"There are {len(self._operator_reference.fleet.vehicles_below_soc_threshold(self._state_of_charge_threshold))} vehicles with low state of charge.",  # noqa: G004
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

            logging.info(
                f"Charging Tasks scheduled. In total {len(charging_events)} charging tasks are generated. Count: {no_vehicles_scheduled_to_charge}",  # noqa: G004
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

                relocations = self.generate_relocation_plan()

                # We track the charging events
                relocation_events = []

                # No Vehicles to be charged
                no_vehicles_scheduled_to_relocate = {}

                for mode in self._available_vehicle_modes:
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
                                    self._operator_reference.fleet,
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
                                self._operator_reference.fleet,
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
                self._operator_reference._workforce.task_queue.bulk_append(  # noqa: SLF001
                    self._scheduled_tasks
                )

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

    def generate_relocation_plan(self):  # noqa: ANN201
        """

        Return relocation plan
        :param transactions: Simulation Transactions to calculate Fleet State and Expected In/Outlflows (from PaymentEngine)
        :return: Dict of potential relocations {"SharedCar": [(origin, destination, no, distance)], ..}
        """
        fleet_state = self.calculate_residual_supply(
            self._operator_reference.fleet, self.operator.demand_monitor
        )

        relocation_plans = self.identify_potential_relocations(fleet_state)

        return relocation_plans

    def generate_charging_plan(self):  # noqa: ANN201
        """
        Generate a rule based charging plan based on given service worker capacity
        :param transactions: Simulation Transactions to calculate Fleet State and Expected In/Outlflows
        :return: **charging_plan**: Dictionary with keys for vehicle modes and values with lists of multiple
                charging tasks
                **used_capacity**: How many service workers are planned to cope with charging needs
        """
        # Get Current Fleet State
        state = self.calculate_residual_supply(
            self._operator_reference.fleet, self._operator_reference.demand_monitor
        )

        config = Configuration()
        if config.settings.PERSIST_RESULTS:
            state.to_csv(
                Path(config.path.OUTPUT_FOLDER, config.path.FLEET_STATE_FILE),
                index=False,
            )

        charging_plans, used_capacity = self.calculate_charging_plan(state)

        return charging_plans, used_capacity

    #############################################
    #############################################
    #  Charging Planing                         #
    #############################################
    #############################################

    def calculate_charging_plan(self, fleet_state):  # noqa: ANN001, ANN201
        """
        :param fleet_state: Represent current fleet state (output from function calculate_residual_supply)
        :param distance_matrix: Distance between Regions
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
        state = fleet_state

        # How much capacity is already "used"
        # free_base_capacity = dict(
        #     zip(self._base_regions, [self._base_capacity] * len(self._base_regions))
        # )

        # Split available service worker resources among vehicle types
        # (prioritize vehicles where most low soc vehicles are present)
        capacity_per_mode = self.calculate_resource_capacity_split_for_charging(
            state,
            self._available_vehicle_modes,
            self._max_vehicle_supply,
            self._operator_reference._workforce.number_service_workers,  # noqa: SLF001
        )

        # We calculate for each vehicle mode dedicated charging plans based on the available resources
        all_charging_plans = {}

        for i, mode in enumerate(self._available_vehicle_modes):
            # Sort State by Regions with highest number of SoC (per vehicle)
            state = state.sort_values(
                by=[f"{mode}_Low_SoC", "hex_id"], ascending=[False, True]
            )

            # Get Max Charging Capacity per Service Worker Unit
            # e.g., 40 Kick Scooters by one SW, 1 Car by one SW
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Mode Specific Service Unit Resources (i.e., how many service workers have we assigned to collect the current mode)
            number_service_workers_per_mode = capacity_per_mode[i]

            # Keep track of vehicles which are already scheduled for pick up and charging per region
            already_scheduled_low_vehicles = {}

            # Resulting charging plan having charging tasks per service worker
            # Each element represents one pick up and charging task
            # each element can consist of multiple tasks since vehicles from nearby regions can also be collected if
            # space if available.
            # Example [(origin, destination, number of vehicles to pick up, destination to base)]
            # Multitask Example
            # [
            #  ('871f1d49dffffff', '871f1d488ffffff', 24.0, 4173.489610482256),
            #  ('871f1d48effffff', '871f1d488ffffff', 16.0, 2312.641785385671) <- This is the neighbour of 871f1d49dffffff, distance to neighbour
            # ]
            # Note that the first element has the distance to the base and all other elements are relative to the first (main) region.
            charging_plan = []

            for index, row in state.iterrows():
                next_hex_id = row["hex_id"]

                # Break loop if service worker resources are depleted
                if len(charging_plan) == number_service_workers_per_mode:
                    # No more service worker capacity, stop planning
                    break

                # Get nearest fleet base region (.loc -> destination, [[]] -> Origin)
                sorted_base_list = self._distance_matrix.loc[self._base_regions][
                    [next_hex_id]
                ].sort_values(by=next_hex_id, ascending=True)

                # How many vehicles are already schedules for pick up?
                if next_hex_id not in already_scheduled_low_vehicles:
                    already_scheduled_low_vehicles[next_hex_id] = 0

                # Select Nearest Base
                for index_base, row_base in sorted_base_list.iterrows():
                    selected_base = index_base
                    selected_base_distance = row_base[next_hex_id]

                while (
                    len(charging_plan) != number_service_workers_per_mode
                    and already_scheduled_low_vehicles[next_hex_id]
                    != row[f"{mode}_Low_SoC"]
                ):
                    # Keep Track of how many vehicles are already scheduled for charging
                    currently_schedules_vehicles_per_unit = 0

                    # How many vehicles can we move to the base and charge?
                    pick_up_vehicles = min(
                        (
                            row[f"{mode}_Low_SoC"]
                            - already_scheduled_low_vehicles[next_hex_id]
                        ),
                        max_capacity_per_unit,
                    )

                    # currently_schedules_vehicles_per_unit
                    currently_schedules_vehicles_per_unit += pick_up_vehicles

                    # Update Already Picked Up Vehicle Dict
                    already_scheduled_low_vehicles[next_hex_id] += pick_up_vehicles

                    # Collection of Charging Tasks per Service Worker
                    chargings_tasks = []

                    # Charging Task from current region to fleet base
                    charging_task = (
                        next_hex_id,
                        selected_base,
                        pick_up_vehicles,
                        selected_base_distance,
                    )

                    # Add main chargin task to charging tasks
                    if pick_up_vehicles > 0:
                        chargings_tasks.append(charging_task)

                    # If we still have capacity, and no more vehicles are in the region
                    if (
                        pick_up_vehicles < max_capacity_per_unit
                        and pick_up_vehicles > 0
                    ):
                        neighbours = h3.hex_range(next_hex_id, 1)
                        neighbours.remove(
                            next_hex_id
                        )  # Consider only neighbours (not current region)

                        # Consider only Fleet State of neighbour regions
                        neighbour_states = state[state["hex_id"].isin(neighbours)]

                        for index_adjacent, row_adjacent in neighbour_states.iterrows():
                            adjacent_hex_id = row_adjacent["hex_id"]

                            # How many vehicles from the adjacent regions are already schedules for pick up?
                            if adjacent_hex_id not in already_scheduled_low_vehicles:
                                already_scheduled_low_vehicles[adjacent_hex_id] = 0

                            # How many vehicles can we move from the adjacent hex to the base and charge them?
                            pick_up_vehicles_from_adjacent_region = min(
                                (
                                    row_adjacent[f"{mode}_Low_SoC"]
                                    - already_scheduled_low_vehicles[adjacent_hex_id]
                                ),
                                max_capacity_per_unit
                                - currently_schedules_vehicles_per_unit,
                            )

                            # Can we pick up any vehicles from that neighbour? If yes, append charging task
                            if pick_up_vehicles_from_adjacent_region > 0:
                                # currently_schedules_vehicles_per_unit
                                currently_schedules_vehicles_per_unit += (
                                    pick_up_vehicles_from_adjacent_region
                                )

                                # Update Already Picked Up Vehicle Dict
                                already_scheduled_low_vehicles[adjacent_hex_id] += (
                                    pick_up_vehicles_from_adjacent_region
                                )

                                # Distance to Neighbour
                                distance_to_neighbour = self._distance_matrix.loc[
                                    adjacent_hex_id
                                ][next_hex_id]

                                # add additional charging task
                                charging_task = (
                                    adjacent_hex_id,
                                    selected_base,
                                    pick_up_vehicles_from_adjacent_region,
                                    distance_to_neighbour,
                                )

                                # Add to Charging Tasks list (i.e., this is a multitask object; one service workers needs to visit multiple regions)
                                chargings_tasks.append(charging_task)

                    # Store Charging Task
                    if len(chargings_tasks) > 0:
                        charging_plan.append(chargings_tasks)

            # Save Charging Plan of Vehicle Mode
            all_charging_plans[mode] = charging_plan

        # Count planned resources (e.g., service workers needed to execute planned charging jobs)
        used_resources = 0
        for key in all_charging_plans:
            used_resources += len(all_charging_plans[key])

        return all_charging_plans, used_resources

    def calculate_resource_capacity_split_for_charging(  # noqa: ANN201
        self,
        fleet_state,  # noqa: ANN001
        available_vehicle_modes,  # noqa: ANN001
        max_vehicle_supply,  # noqa: ANN001
        number_service_workers_per_mode,  # noqa: ANN001
    ):
        """
            Determine Service Worker Split Between Modes (How many workers should be assigned to charge how many vehicles)

            Process: Calculate Fraction of Low SOC Vehicles per Mode. Then calculate weighted sum.
                1. frac_i = #low_soc_vehicle_i*weight_i/max_vehicle_supply_i
                    1.1. We calculate weight as the inverse of "get_max_capacity_per_unit" for each vehicle mode
                    1.2. Thus, we ensure that not too many service workers are assigned to vehicles that can be pooled
                2. total_frac = sum frac_i
                3. Calculate how many service workers are assigned to charge vehicle mode i
                   capacity_i = frac_i/total_frac * number_service_workers_i
        :param fleet_state: Resulting data frame from function calculate_residual_supply
        :param available_vehicle_modes: List of available vehicle modes (["SharedKickScooter", "SharedScooter", "SharedCar"]
        :param max_vehicle_supply: List of maximum number of available vehicles (order is aligned with available_vehicle_modes)
                                for example: [10, 5, 12] => 10 kick scooter, 5 scooter, 12 cars
        :param number_service_workers: Available Service Worker Capacity
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
            curr_low_supply / max_supply if max_supply != 0 else 0
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

        capacity = capacity_fraction * number_service_workers_per_mode

        capacity = [round(x) for x in capacity]

        # Rounding Fractions => Sum of Residual don't add up to available units
        # We fix this by adding or subtracting the residual to the max. element
        # Happens very rarely
        residual = number_service_workers_per_mode - sum(capacity)

        max_element = max(capacity)
        arg_max = capacity.index(max_element)

        if residual > 0:
            # We add excess supply to mode where most workforce is needed
            capacity[arg_max] += residual
        elif residual < 0:
            capacity[arg_max] = max(capacity[arg_max] + residual, 0)

        return capacity

    def get_max_capacity_per_unit(self, mode):  # noqa: ANN001, ANN201
        # Mode Specific Collection Capacity per Service Worker (i.e., how many vehicles can one sw collect)
        if mode == "KickScooter":
            max_capacity_per_unit = 40
        elif mode == "Bike":
            max_capacity_per_unit = 8
        elif mode == "Scooter":
            max_capacity_per_unit = 8
        elif mode == "Car":
            max_capacity_per_unit = 1
        else:
            raise NotImplementedError("Not Implemented")
        return max_capacity_per_unit

    #############################################
    #############################################
    #  Relocation Planing                       #
    #############################################
    #############################################

    def identify_potential_relocations(self, state):  # noqa: ANN001, ANN201
        """
        Calculate how many vehicles need to be moved (or can be) from origin to destination

          Approach:Calculate state of the fleet. Relocate vehicles from regions with positive residual (excess of vehicles)
          to regions with negative residuals (lack of vehicles). We differentiate between two types of relocations.

          Single Vehicle and Pooled Relocations. Cars for example are single relocation, kick scooters are relocated in a pooled fashion.

          The single relocation case is simple. Relocate vehicles from nearest regions with excess vehicle supply.

          The pooled relocation process is more complicated. First, we identify the target region with lack of
          vehicle supply. Typically, we begin with the region with vehicle lack. We then find regions nearby
          where vehicles are abundant. Then, we try to relocate as much vehicles from that region to the target region.
          In general, we try to avoid pooling vehicles from multiple region (i.e., deplete supply in a region).

          However, if there is space left for other vehicles within the relocation pool, we spot the next region
          where vehicles are available. We continue until the pooling capacity is reached. After having identified
          the candidate regions along with the vehicles to be relocated, we calculate the shortest pick up route
          by solving the traveling salesman problem.

        :param state: Output of function compute_relocations
        :return: Dictionary with relocation strategies for each vehicle mode under consideration
            - e.g., "SharedScooter": [
            [("origin", "destination", No_Vehicles_To_Move, Distance)],
            [("origin_x", "destination_z", No_Vehicles_To_Move, Distance), ("origin_y", "destination_z", No_Vehicles_To_Move, Distance)]
            ]
        """
        relocations = {}

        # Split available service worker resources among vehicle types
        # (prioritize vehicles where most low soc vehicles are present)
        capacity_per_mode = self.calculate_resource_capacity_split_for_relocation(
            state,
            self._available_vehicle_modes,
            self._max_vehicle_supply,
            self._operator_reference._workforce.number_service_workers,  # noqa: SLF001
        )
        for i, mode in enumerate(self._available_vehicle_modes):
            # Relocation List containing tuples (origin, destination, number_of_vehicles_to_be_relocated, distance)
            relocation_list = []

            relocations[mode] = relocation_list

            # Get Max Charging Capacity per Service Worker Unit
            # e.g., 40 Kick Scooters by one SW, 1 Car by one SW
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Mode Specific Service Unit Resources (i.e., how many service workers have we assigned to collect the current mode)
            number_service_workers_per_mode = capacity_per_mode[i]

            # Already Relocated Vehicles
            hexagons = list(state["hex_id"].unique())
            already_relocated = dict(zip(hexagons, [0] * len(hexagons)))

            # Sort Ascending
            state = state.sort_values(by=[f"Residual_Supply_{mode}"])

            for index, next_hex in state[
                state[f"Residual_Supply_{mode}"] < 0
            ].iterrows():
                """
                  Iterate through each hexagon where we expect a negative supply (i.e., demand and supply don't match)
                  Start with hexagon with highest lack of vehicle supply
                """
                next_hex_id = next_hex["hex_id"]
                residual_supply = next_hex[f"Residual_Supply_{mode}"]

                # Already Relocated Vehicles into this Hexagon
                relocated_vehicles = 0

                # Break loop if service worker resources are depleted
                if len(relocation_list) == number_service_workers_per_mode:
                    # No more service worker capacity, stop planning
                    break

                # Get Distance To All Other Regions
                sub_distance_matrix = self._distance_matrix[[next_hex_id]].reset_index()
                sub_distance_matrix.rename(columns={"index": "hex_id"}, inplace=True)

                # Merge Sub Distance Matrix of selected Region with Relocation Plan
                # We obtain for the current hexagon a list of all hexagons along with their current vehicle supply
                distance_to_other_hexagons = sub_distance_matrix.merge(
                    state, how="inner", on="hex_id"
                )

                # Sort by distance (in meter) (i.e., prefer neighbours first)
                distance_to_other_hexagons = distance_to_other_hexagons.sort_values(
                    by=[next_hex_id]
                )

                # Only consider regions having additional supply
                distance_to_other_hexagons = distance_to_other_hexagons[
                    distance_to_other_hexagons[f"Residual_Supply_{mode}"] > 0
                ]
                distance_to_other_hexagons[f"Relocate_{mode}"] = 0

                # Calculate for the current hexagon the number of vehicles to be relocated from other regions.
                idx = []
                local_relocation_schedule = []

                for index, row in distance_to_other_hexagons.iterrows():
                    # Minimum between available vehicles (i.e., only relocate vehicles which are there, now!)
                    vehicle_buffer = 3
                    # -3 is our buffer
                    physicially_available_vehicles = min(
                        row[f"Residual_Supply_{mode}"],
                        max(row[f"{mode}"] - vehicle_buffer, 0),
                    )

                    if physicially_available_vehicles <= 0:
                        continue  # We cannot use this region to get vehicles

                    # Relocatable Vehicles = Additional Vehicles - Already (Planned) for Relocation Vehicles
                    relocatable_vehicles = (
                        physicially_available_vehicles
                        - already_relocated[row["hex_id"]]
                    )
                    # We relocate only either the availalbe number of relocatable vehicles or missing number of vehicles
                    relocate = min(
                        relocatable_vehicles, abs(residual_supply) - relocated_vehicles
                    )

                    # Increment relocated vehicles counter
                    relocated_vehicles += relocate

                    # How many vehicles are still left in that hexagon
                    # Important for the determination of vehicle relocations for remaining regions
                    already_relocated[row["hex_id"]] += relocate

                    # We use lists here and append them later to the DataFrame
                    idx.append(index)
                    local_relocation_schedule.append(relocate)

                # Break loop if there is no "excess" supply
                if len(local_relocation_schedule) == 0:
                    logging.info(
                        f"Cannot calculate relocation plan for {mode} as there are no regions with excess supply.",  # noqa: G004
                        extra={"clazz": self.__class__.__name__, "oid": ""},
                    )
                    break

                # Append No. of Vehicles to be relocated
                distance_to_other_hexagons[f"Relocate_{mode}"] = pd.DataFrame(
                    local_relocation_schedule, index=idx
                )

                # Pool Relocations and split tasks by capacity of each service worker.
                tmp_list = []
                tmp_counter = 0
                for index, row in distance_to_other_hexagons[
                    distance_to_other_hexagons[f"Relocate_{mode}"] > 0
                ].iterrows():
                    # First create relocation jobs that can immediately provide vehicles without "visiting" nearby areas
                    while (
                        distance_to_other_hexagons.loc[index, f"Relocate_{mode}"]
                        >= max_capacity_per_unit
                        and len(relocation_list) < number_service_workers_per_mode
                    ):
                        relocation_list.append(
                            [
                                (
                                    row["hex_id"],
                                    next_hex_id,
                                    max_capacity_per_unit,
                                    row[next_hex_id],
                                )
                            ]
                        )
                        distance_to_other_hexagons.loc[index, f"Relocate_{mode}"] = (
                            distance_to_other_hexagons.loc[index, f"Relocate_{mode}"]
                            - max_capacity_per_unit
                        )

                    if len(relocation_list) == number_service_workers_per_mode:
                        # No more service worker capacity, stop planning
                        break

                    # Remaining capacity of service worker
                    local_missing_supply = max_capacity_per_unit - tmp_counter

                    local_relocatable_vehicles = min(
                        distance_to_other_hexagons.loc[index, f"Relocate_{mode}"],
                        local_missing_supply,
                    )

                    # Pool Relocation Tasks as worker has still some capacity
                    if (
                        tmp_counter + local_relocatable_vehicles
                        <= max_capacity_per_unit
                        and local_relocatable_vehicles > 0
                    ):
                        tmp_list.append(
                            (
                                row["hex_id"],
                                next_hex_id,
                                local_relocatable_vehicles,
                                row[next_hex_id],
                            )
                        )
                        tmp_counter += local_relocatable_vehicles

                        # Update relocatable vehicles (such that next service worker can also process remaining vehicles)
                        distance_to_other_hexagons.loc[index, f"Relocate_{mode}"] = (
                            distance_to_other_hexagons.loc[index, f"Relocate_{mode}"]
                            - local_relocatable_vehicles
                        )
                    else:
                        # Start new pooled task as capacity is depleted of current service worker.
                        # List of (Origin, Destination, No. Vehicles to Relocate, Distance from Origin to Distance)
                        if len(tmp_list) > 0:
                            relocation_list.append(tmp_list)

                        # Reset
                        tmp_list = []
                        tmp_counter = 0

                if (
                    len(relocation_list) < number_service_workers_per_mode
                    and len(tmp_list) > 0
                ):
                    relocation_list.append(tmp_list)

            # If multiple hexagons are visited to pick up vehicles, we need to solve the traveling salesman problem
            for relocation in relocation_list:
                if len(relocation) > 1:
                    hexagons = {}

                    for tuple_idx, tuple in enumerate(relocation):
                        origin, destination, vehicle_count, distance = tuple

                        # We relocate vehicles to this position => Index 0
                        if tuple_idx == 0:
                            hexagons[destination] = tuple_idx

                        # From here
                        hexagons[origin] = tuple_idx + 1

                    tsp_result = solve_tsp(hexagons, self._distance_matrix)
                    tour_sequence, tour_length, dist_lookup = (
                        tsp_result.tour_sequence,
                        tsp_result.tour_length,
                        tsp_result.distance_lookup,
                    )

                    # Find the predecessor and successor of destination in the tour
                    index_of_destination = tour_sequence.index(0)
                    predecessor_idx = (index_of_destination - 1) % len(tour_sequence)
                    successor_idx = (index_of_destination + 1) % len(tour_sequence)

                    # Compare costs of the two possible edges to remove
                    cost_entering_dest = dist_lookup.get(
                        tour_sequence[predecessor_idx],
                        tour_sequence[index_of_destination],
                    )

                    cost_exiting_dest = dist_lookup.get(
                        tour_sequence[index_of_destination],
                        tour_sequence[successor_idx],
                    )

                    if cost_entering_dest > cost_exiting_dest:
                        # Remove edge entering destination by placing destination at the start
                        tour_sequence = (
                            tour_sequence[index_of_destination:]
                            + tour_sequence[:index_of_destination]
                        )
                        excess_distance = cost_entering_dest
                    else:
                        # Remove edge exiting destination by placing destination at the end
                        tour_sequence = (
                            tour_sequence[(index_of_destination + 1) :]
                            + tour_sequence[: (index_of_destination + 1)]
                        )
                        excess_distance = cost_exiting_dest

                    # Remove the distance from the "destination" to the "origin" of the relocation trip
                    total_distance = tour_length - excess_distance

                    average_distance_per_relocation_step = total_distance / len(
                        relocation
                    )

                    # Save old tuples
                    old_relocation = relocation.copy()

                    # Remove old tuples
                    relocation.clear()

                    # Override distances based on calculated traveling salesman problem solution
                    for elem in old_relocation:
                        tmp_elem = list(elem)
                        tmp_elem[3] = average_distance_per_relocation_step
                        tmp_elem = (*tmp_elem,)

                        relocation.append(tmp_elem)

        return relocations

    def calculate_resource_capacity_split_for_relocation(  # noqa: ANN201
        self,
        fleet_state,  # noqa: ANN001
        available_vehicle_modes,  # noqa: ANN001
        max_vehicle_supply,  # noqa: ANN001
        number_service_workers_per_mode,  # noqa: ANN001
    ):
        """
            Determine Service Worker Split Between Modes (How many workers should be assigned to relocate how many vehicles)

            We calculate the L1 Norm for each mode based on a "stable" vehicle networks (i.e, supply demand mismatch = 0).
            L1 = Sum (abs(Residual))
            Normalize L1 with vehicle capacity per service worker => L1_n = L1/weight_i (i.e,e L1/40 for kick scooters)
        :return: List of assigned resource workers to vehicle modes (order is aligned with available_vehicle_modes)
                        for example: Input 25 Service Workers
                                    => [5, 5, 10] <=> 5 sw for kick scooter, and scooter, 10 for cars.
        """

        current_supply_mismatch = []

        max_unit_assignment = []

        for idx, mode in enumerate(self._available_vehicle_modes):
            # Service Worker Relocation Capacity per Mode
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Normalize the vehicle weight;
            # One Service Worker can "process" 40 units of kick scooters compared to 1 sw for one car.
            current_supply_mismatch.append(
                fleet_state[f"Residual_Supply_{mode}"].abs().sum()
                / max_capacity_per_unit
            )

            max_unit_assignment.append(
                round(max_vehicle_supply[idx] / max_capacity_per_unit + 0.49)
            )  # Round Up

        # Normalize by number of vehicles
        current_supply_mismatch = [
            supply_mismatch / max_supply if max_supply != 0 else 0
            for supply_mismatch, max_supply in zip(
                current_supply_mismatch, max_vehicle_supply
            )
        ]

        # Temporary Denom
        denominator = sum(current_supply_mismatch)

        if denominator == 0.0:
            # No Relocations Needed => No Workers assigned
            return len(current_supply_mismatch) * [0]

        # Split capacity based on the following fraction
        capacity_fraction = current_supply_mismatch / denominator

        capacity = capacity_fraction * number_service_workers_per_mode

        capacity = [round(x) for x in capacity]

        capacity = [
            min(capa, max_unit_assign)
            for capa, max_unit_assign in zip(capacity, max_unit_assignment)
        ]

        # Rounding Fractions => Sum of Residual don't add up to available units
        # We fix this by adding or subtracting the residual to the max. element
        # Happens very rarely
        residual = number_service_workers_per_mode - sum(capacity)

        # Residual ensures that we deplete all available service workers
        # the second condition ensures that we only do this until we have reached "needed" capacity to do operations.
        # For example: If we have very low number of vehicles, but a high number of service workers,
        #              we will have a lot residuals but we don't need them as capacity is already equal max_unit_assignment.
        while residual > 0 and sum(capacity) < sum(max_unit_assignment):
            for idx, elem in enumerate(capacity):
                if residual > 0:
                    if capacity[idx] < max_unit_assignment[idx]:
                        capacity[idx] += 1
                        residual -= 1
        return capacity

    #############################################
    #############################################
    #  Fleet State Analysis                     #
    #############################################
    #############################################

    def calculate_residual_supply(
        self, vehicle_fleet: MixedSharedVehicleFleet, demand_monitor: DemandMonitor
    ) -> pd.DataFrame:
        """
        Calculate relocation strategy based on (expected) demand, supply and vehicles to be charged.

        Parameters
        ----------
        vehicle_fleet : MixedSharedVehicleFleet
            Mixed vehicle fleet object.
        demand_monitor : DemandMonitor
            The demand monitor containing incremental demand statistics.

        Returns
        -------
        pd.DataFrame
            Fleet state with residual supply calculations.
        """
        # Get Vehicle Supply per Hexagon
        supply = vehicle_fleet.supply_per_region()
        supply_df = pd.DataFrame(supply).T.reset_index()
        supply_df.rename(columns={"index": "hex_id"}, inplace=True)

        # Get Low SoC Vehicle Supply per Hexagon
        low_soc_supply = vehicle_fleet.vehicles_to_be_charged_per_region(
            self._state_of_charge_threshold
        )
        df_low_soc = pd.DataFrame(low_soc_supply).T.reset_index()
        df_low_soc.rename(columns={"index": "hex_id"}, inplace=True)

        # Get Expected Demand (Delta) per Hexagon
        expected_demand = self.aggregate_delta_demand(demand_monitor)

        # Merge Demand, Supply and Low SoC Vehicles
        fleet_state = expected_demand.merge(supply_df, how="outer", on="hex_id")
        fleet_state = fleet_state.merge(
            df_low_soc, how="outer", on="hex_id", suffixes=("", "_Low_SoC")
        )
        fleet_state.fillna(0, inplace=True)

        # Calculate Residual Supply for each vehicle type
        for vehicle in self._available_vehicle_modes:
            # TODO: Make this dependent on vehicle drive, not mode
            if vehicle == "SharedBike":
                fleet_state[f"Residual_Supply_{vehicle}"] = (
                    fleet_state[vehicle] + fleet_state[f"Delta_{vehicle}"]
                )
            else:
                fleet_state[f"Residual_Supply_{vehicle}"] = (
                    fleet_state[vehicle]
                    - fleet_state[f"{vehicle}_Low_SoC"]
                    + fleet_state[f"Delta_{vehicle}"]
                )

        return fleet_state

    def aggregate_delta_demand(self, demand_monitor: DemandMonitor) -> pd.DataFrame:
        """
        Compute net vehicle flow (vehicle surplus or excess demand) for each hexagon and vehicle type.

        For each region (hexagon) and vehicle mode, this function calculates the net vehicle flow as the
        difference between the number of vehicles arriving (inflow) and the total outflow, where outflow
        is the sum of fulfilled departures and missed demand (unfulfilled requests). The result is a
        DataFrame with one row per hexagon and columns for inflow, fulfilled outflow, missed outflow,
        and net vehicle flow for each vehicle type.

        Parameters
        ----------
        demand_monitor : DemandMonitor
            Demand monitor containing cumulative demand statistics for each hexagon and vehicle type.

        Returns
        -------
        pd.DataFrame
            DataFrame with one row per hexagon and the following columns for each vehicle type:
            - 'Inflow_<vehicle>': int
                Number of vehicles arriving at the hexagon.
            - 'OutFlow_Fulfilled_<vehicle>': int
                Number of fulfilled departures from the hexagon.
            - 'OutFlow_Missed_<vehicle>': int
                Number of missed departures (unfulfilled requests) from the hexagon.
            - 'Delta_<vehicle>': int
                Net vehicle flow: inflow - outflow_fulfilled - outflow_missed.

        Notes
        -----
        - Outflow is the sum of fulfilled departures and missed demand (unfulfilled requests).
        - A negative delta indicates excess demand (more departures or missed requests than arrivals).
        - A positive delta indicates a vehicle surplus (more arrivals than departures).
        """
        vehicle_demand: VehicleDemandByRegion = demand_monitor.get_demand_data()
        ordered_available_vehicle = demand_monitor.ordered_available_vehicles

        rows = []
        for hex_id in vehicle_demand.keys():
            row: dict[str, int | str] = {"hex_id": hex_id}
            for vehicle in ordered_available_vehicle:
                inflow = (
                    vehicle_demand.get(hex_id, {}).get(vehicle, {}).get("inflow", 0)
                )
                outflow_fulfilled = (
                    vehicle_demand.get(hex_id, {})
                    .get(vehicle, {})
                    .get("outflow_fulfilled", 0)
                )
                outflow_missed = (
                    vehicle_demand.get(hex_id, {})
                    .get(vehicle, {})
                    .get("outflow_missed", 0)
                )
                row[f"Inflow_{vehicle}"] = inflow
                row[f"OutFlow_Fulfilled_{vehicle}"] = outflow_fulfilled
                row[f"OutFlow_Missed_{vehicle}"] = outflow_missed
                row[f"Delta_{vehicle}"] = inflow - outflow_fulfilled - outflow_missed
            rows.append(row)
        return pd.DataFrame(rows)
