import logging
from pathlib import Path

import h3
import six
import sys

from simulation.operator.operations_management.integrated_strategy import IntegratedStrategy
from simulation.operator.operations_management.service_tasks.charging_task import ChargingTask
from simulation.operator.operations_management.service_tasks.multi_service_task import MultiServiceTask
from simulation.operator.operations_management.shared_mobility_strategy import SharedMobiltyStrategy
from simulation.operator.vehicle_fleet import VehicleFleet
sys.modules['sklearn.externals.six'] = six
import mlrose as mlrose
import pandas as pd

from simulation.helper.configuration.configuration import Configuration

class IntegratedSharedMobilityStrategy(SharedMobiltyStrategy, IntegratedStrategy):

    #TODO: refactor base_regions and capacity, such that it relates to the infrastructure of the operator. This also implies that we need to register the infrastructure after the opeartor is initialised

    def __init__(self, env, distance_matrix, ordered_available_vehicle_modes,
                 ordered_max_vehicle_supply, base_regions, base_capacity):
        super(IntegratedSharedMobilityStrategy, self).__init__(env = env)
        # Distance Matrix between Regions
        self._distance_matrix = distance_matrix

        # List needs to be ordered such that:
        # In case of neutral demand, we count the demand for the less expensive option
        # For example: If we observe a demand for KickScooter and Scooter, we count that
        # demand to KickScooter. This ordering is defined according to the following list
        # (from left to right)
        self._available_vehicle_modes = ordered_available_vehicle_modes
        self._max_vehicle_supply = ordered_max_vehicle_supply
        self._base_regions = base_regions
        self._base_capacity = base_capacity

        self._scheduled_tasks = []

    def refuel_fleet(self, fleet: VehicleFleet):
        #TODO: Refactor stuff from main and operator, such that the operator only has to call strategy.refuel_fleet()
        self._fleet = fleet

        """"
        Below, we combine the old operational logic from operations.py and relocation_strategy.py
        """

        # Clean old jobs (if there are some left)
        self._service_workforce.task_queue.clear()

        # TODO: how do we get transactions from operator? / do we need transactions here?
        # Retrieve Vehicle Transactions
        # transactions = self._payment_engine.get_transactions()

        # Retrieve Charging Plan to Charge Vehicles with low State of Charge
        charging_plans, used_capacity = self.generate_charging_plan(transactions)

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
                        origin, destination, no_vehicle_to_charge, distance_to_base = task

                        charging_task = ChargingTask(self._env, origin, destination, no_vehicle_to_charge, mode, distance_to_base,
                                        self._fleet, self._state_of_charge_threshold)

                        multi_service_task.append_task(charging_task)

                        # Count Vehicles to be charged
                        no_vehicles_scheduled_to_charge[mode] += no_vehicle_to_charge

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

                    # Count Vehicles to be charged
                    no_vehicles_scheduled_to_charge[mode] += no_vehicle_to_charge

        # Insert Tasks into Task Queue
        self._task_queue.bulk_append(self._scheduled_tasks)

        logging.info(f"There are {self._vehicle_fleet.get_all_vehicles_below_soc_level(self._state_of_charge_threshold)} vehicles with low state of charge.",
            extra={"clazz": self.__class__.__name__, "oid": ""})

        logging.info(f"Charging Tasks scheduled. In total {len(charging_events)} charging tasks are generated. Count: {no_vehicles_scheduled_to_charge}",
            extra={"clazz": self.__class__.__name__, "oid": ""})

        # Notify listeners
        self._charging_plan_updated.succeed()
        self._charging_plan_updated = self._env.event()

        # While Shift is not over, recalculate relocation plans and execute them.
        while self._env.now % self._time_between_operations < self._duration_of_operations:
            logging.info(f"Planning next relocation schedule.",
                            extra={"clazz": self.__class__.__name__, "oid": ""})

            # Reset Scheduled Tasks
            self._scheduled_tasks.clear()

            # Wait 2 Minutes, then (re-)schedule relocation
            yield self._env.timeout(2)

            transactions = self._payment_engine.get_transactions()

            relocations = self._relocation_scheduler.generate_relocation_plan(transactions)

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
                            origin, destination, no_vehicle_to_relocate, relocation_distance = task

                            relocation_task = RelocationTask(self._env, origin, destination, no_vehicle_to_relocate, relocation_distance, mode,
                                            self._vehicle_fleet)

                            multi_service_task.append_task(relocation_task)

                            # Count Vehicles to be charged
                            no_vehicles_scheduled_to_relocate[mode] += no_vehicle_to_relocate

                        # Schedule to Queue
                        self._scheduled_tasks.append(multi_service_task)

                        # Remember event for multi service tasks
                        relocation_events.append(multi_service_task.task_finished)
                    else:
                        # Single Task
                        origin, destination, no_vehicle_to_relocate, relocation_distance = relocation_plan[0]

                        relocation_task = RelocationTask(self._env, origin, destination, no_vehicle_to_relocate,
                                                            relocation_distance, mode,
                                                            self._vehicle_fleet)

                        # Schedule to Queue
                        self._scheduled_tasks.append(relocation_task)

                        # Remember event for multi service tasks
                        relocation_events.append(relocation_task.task_finished)

                        # Count Vehicles to be charged
                        no_vehicles_scheduled_to_relocate[mode] += no_vehicle_to_relocate

            # Insert Tasks into Task Queue
            self._task_queue.bulk_append(self._scheduled_tasks)

            if len(charging_events):
                # Wait for Charging events
                yield self._env.all_of(charging_events)

                logging.info(f"All Charging Tasks have been fulfilled. Re-Generating Relocation Plan.",
                    extra={"clazz": self.__class__.__name__, "oid": ""})

            # Wait for relocation events to be processed
            yield self._env.all_of(relocation_events)

            logging.info(f"Planned Relocation Tasks have been fulfilled. Re-Generating Relocation Plan.",
                            extra={"clazz": self.__class__.__name__, "oid": ""})

    def relocate_fleet(self, fleet: VehicleFleet):
        """
        For the integrated strategy, we don't need to do anything, since self.refuel_fleet() handles both refueling and relocation
        :param fleet: this is the VehicleFleet
        :return: Nothing
        """
        pass 

    def generate_relocation_plan(self, transactions):
        """

        Return relocation plan
        :param transactions: Simulation Transactions to calculate Fleet State and Expected In/Outlflows (from PaymentEngine)
        :return: Dict of potential relocations {"SharedCar": [(origin, destination, no, distance)], ..}
        """
        state = self.calculate_residual_supply(self._fleet, transactions)

        relocation_plans = self.identify_potential_relocations(state)

        return relocation_plans

    def generate_charging_plan(self, transactions):
        """
        Generate a rule based charging plan based on given service worker capacity
        :param transactions: Simulation Transactions to calculate Fleet State and Expected In/Outlflows
        :return: **charging_plan**: Dictionary with keys for vehicle modes and values with lists of multiple
                charging tasks
                **used_capacity**: How many service workers are planned to cope with charging needs
        """
        # Get Current Fleet State
        state = self.calculate_residual_supply(self._fleet, transactions)

        config = Configuration.instance()
        if config.store_results:
            state.to_csv(Path(config.output_path, config.fleet_state_file), index = False)

        charging_plans, used_capacity = self.calculate_charging_plan(state)

        return charging_plans, used_capacity

    #############################################
    #############################################
    #  Charging Planing                         #
    #############################################
    #############################################


    def calculate_charging_plan(self, fleet_state):
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
        free_base_capacity = dict(zip(self._base_regions, [self._base_capacity] * len(self._base_regions)))

        # Split available service worker resources among vehicle types
        # (prioritize vehicles where most low soc vehicles are present)
        capacity_per_mode = self.calculate_resource_capacity_split_for_charging(state, self._available_vehicle_modes, self._max_vehicle_supply,
                                                                                self._service_workforce.number_service_workers)

        # We calculate for each vehicle mode dedicated charging plans based on the available resources
        all_charging_plans = {}

        for i, mode in enumerate(self._available_vehicle_modes):
            # Sort State by Regions with highest number of SoC (per vehicle)
            state = state.sort_values(by=[f"{mode}_Low_SoC"], ascending=False)

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
                sorted_base_list = self._distance_matrix.loc[self._base_regions][[next_hex_id]].sort_values(
                    by=next_hex_id,
                    ascending=True)

                # How many vehicles are already schedules for pick up?
                if next_hex_id not in already_scheduled_low_vehicles:
                    already_scheduled_low_vehicles[next_hex_id] = 0

                # Select Nearest Base
                for index_base, row_base in sorted_base_list.iterrows():
                    selected_base = index_base
                    selected_base_distance = row_base[next_hex_id]

                while (len(charging_plan) != number_service_workers_per_mode and
                       already_scheduled_low_vehicles[next_hex_id] != row[f"{mode}_Low_SoC"]):

                    # Keep Track of how many vehicles are already scheduled for charging
                    currently_schedules_vehicles_per_unit = 0

                    # How many vehicles can we move to the base and charge?
                    pick_up_vehicles = min((row[f"{mode}_Low_SoC"] - already_scheduled_low_vehicles[next_hex_id]),
                                           max_capacity_per_unit)

                    # currently_schedules_vehicles_per_unit
                    currently_schedules_vehicles_per_unit += pick_up_vehicles

                    # Update Already Picked Up Vehicle Dict
                    already_scheduled_low_vehicles[next_hex_id] += pick_up_vehicles

                    # Collection of Charging Tasks per Service Worker
                    chargings_tasks = []

                    # Charging Task from current region to fleet base
                    charging_task = (next_hex_id, selected_base, pick_up_vehicles, selected_base_distance)

                    # Add main chargin task to charging tasks
                    if pick_up_vehicles > 0:
                        chargings_tasks.append(charging_task)

                    # If we still have capacity, and no more vehicles are in the region
                    if pick_up_vehicles < max_capacity_per_unit and pick_up_vehicles > 0:
                        neighbours = h3.hex_range(next_hex_id, 1)
                        neighbours.remove(next_hex_id)  # Consider only neighbours (not current region)

                        # Consider only Fleet State of neighbour regions
                        neighbour_states = state[state["hex_id"].isin(neighbours)]

                        for index_adjacent, row_adjacent in neighbour_states.iterrows():
                            adjacent_hex_id = row_adjacent["hex_id"]

                            # How many vehicles from the adjacent regions are already schedules for pick up?
                            if adjacent_hex_id not in already_scheduled_low_vehicles:
                                already_scheduled_low_vehicles[adjacent_hex_id] = 0

                            # How many vehicles can we move from the adjacent hex to the base and charge them?
                            pick_up_vehicles_from_adjacent_region = min(
                                (row_adjacent[f"{mode}_Low_SoC"] - already_scheduled_low_vehicles[adjacent_hex_id]),
                                max_capacity_per_unit - currently_schedules_vehicles_per_unit)

                            # Can we pick up any vehicles from that neighbour? If yes, append charging task
                            if pick_up_vehicles_from_adjacent_region > 0:
                                # currently_schedules_vehicles_per_unit
                                currently_schedules_vehicles_per_unit += pick_up_vehicles_from_adjacent_region

                                # Update Already Picked Up Vehicle Dict
                                already_scheduled_low_vehicles[adjacent_hex_id] += pick_up_vehicles_from_adjacent_region

                                # Distance to Neighbour
                                distance_to_neighbour = self._distance_matrix.loc[adjacent_hex_id][next_hex_id]

                                # add additional charging task
                                charging_task = (adjacent_hex_id, selected_base, pick_up_vehicles_from_adjacent_region,
                                                 distance_to_neighbour)

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


    def calculate_resource_capacity_split_for_charging(self, fleet_state, available_vehicle_modes, max_vehicle_supply, number_service_workers_per_mode):
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
            current_low_soc_supply.append(fleet_state[f"{mode}_Low_SoC"].sum() / max_capacity_per_unit)

        low_fraction_per_mode = [curr_low_supply / max_supply for curr_low_supply, max_supply in
                                 zip(current_low_soc_supply, max_vehicle_supply)]

        # Temporary Denom
        denominator = sum(low_fraction_per_mode)

        if denominator == 0.0:
            # No Charging Needed => No Workers assigned
            return len(low_fraction_per_mode)*[0]

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

    def get_max_capacity_per_unit(self, mode):
        # Mode Specific Collection Capacity per Service Worker (i.e., how many vehicles can one sw collect)
        if mode == "SharedKickScooter":
            max_capacity_per_unit = 40
        elif mode == "SharedScooter":
            max_capacity_per_unit = 8
        elif mode == "SharedCar":
            max_capacity_per_unit = 1
        else:
            raise NotImplementedError("Not Implemented")
        return max_capacity_per_unit

    #############################################
    #############################################
    #  Relocation Planing                       #
    #############################################
    #############################################

    def identify_potential_relocations(self, state):
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
        capacity_per_mode = self.calculate_resource_capacity_split_for_relocation(state, self._available_vehicle_modes,
                                                                                self._max_vehicle_supply,
                                                                                self._service_workforce.number_service_workers)
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

            for index, next_hex in state[state[f"Residual_Supply_{mode}"] < 0].iterrows():
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
                distance_to_other_hexagons = sub_distance_matrix.merge(state, how="inner", on="hex_id")

                # Sort by distance (in meter) (i.e., prefer neighbours first)
                distance_to_other_hexagons = distance_to_other_hexagons.sort_values(by=[next_hex_id])

                # Only consider regions having additional supply
                distance_to_other_hexagons = distance_to_other_hexagons[
                    distance_to_other_hexagons[f"Residual_Supply_{mode}"] > 0]
                distance_to_other_hexagons[f"Relocate_{mode}"] = 0

                # Calculate for the current hexagon the number of vehicles to be relocated from other regions.
                idx = []
                local_relocation_schedule = []

                for index, row in distance_to_other_hexagons.iterrows():
                    # Minimum between available vehicles (i.e., only relocate vehicles which are there, now!)
                    vehicle_buffer = 3
                    # -3 is our buffer
                    physicially_available_vehicles = min(row[f"Residual_Supply_{mode}"], max(row[f"{mode}"]-vehicle_buffer, 0))

                    if physicially_available_vehicles <= 0:
                        continue # We cannot use this region to get vehicles

                    # Relocatable Vehicles = Additional Vehicles - Already (Planned) for Relocation Vehicles
                    relocatable_vehicles = physicially_available_vehicles - already_relocated[row["hex_id"]]
                    # We relocate only either the availalbe number of relocatable vehicles or missing number of vehicles
                    relocate = min(relocatable_vehicles, abs(residual_supply) - relocated_vehicles)

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
                        f"Cannot calculate relocation plan for {mode} as there are no regions with excess supply.",
                        extra={"clazz": self.__class__.__name__, "oid": ""})
                    break

                # Append No. of Vehicles to be relocated
                distance_to_other_hexagons[f"Relocate_{mode}"] = pd.DataFrame(local_relocation_schedule, index=idx)

                # Pool Relocations and split tasks by capacity of each service worker.
                tmp_list = []
                tmp_counter = 0
                for index, row in distance_to_other_hexagons[
                    distance_to_other_hexagons[f"Relocate_{mode}"] > 0].iterrows():

                    # First create relocation jobs that can immediately provide vehicles without "visiting" nearby areas
                    while (distance_to_other_hexagons.loc[index, f"Relocate_{mode}"] >= max_capacity_per_unit
                           and len(relocation_list) < number_service_workers_per_mode):
                        relocation_list.append([(row["hex_id"], next_hex_id, max_capacity_per_unit, row[next_hex_id])])
                        distance_to_other_hexagons.loc[index, f"Relocate_{mode}"] = distance_to_other_hexagons.loc[index, f"Relocate_{mode}"] - max_capacity_per_unit

                    if len(relocation_list) == number_service_workers_per_mode:
                        # No more service worker capacity, stop planning
                        break

                    # Remaining capacity of service worker
                    local_missing_supply = max_capacity_per_unit - tmp_counter

                    local_relocatable_vehicles = min(distance_to_other_hexagons.loc[index, f"Relocate_{mode}"], local_missing_supply)

                    # Pool Relocation Tasks as worker has still some capacity
                    if tmp_counter + local_relocatable_vehicles <= max_capacity_per_unit and local_relocatable_vehicles > 0:
                        tmp_list.append((row["hex_id"], next_hex_id, local_relocatable_vehicles, row[next_hex_id]))
                        tmp_counter += local_relocatable_vehicles

                        # Update relocatable vehicles (such that next service worker can also process remaining vehicles)
                        distance_to_other_hexagons.loc[index, f"Relocate_{mode}"] = distance_to_other_hexagons.loc[index, f"Relocate_{mode}"] - local_relocatable_vehicles
                    else:
                        # Start new pooled task as capacity is depleted of current service worker.
                        # List of (Origin, Destination, No. Vehicles to Relocate, Distance from Origin to Distance)
                        if len(tmp_list) > 0:
                            relocation_list.append(tmp_list)

                        # Reset
                        tmp_list = []
                        tmp_counter = 0

                if len(relocation_list) < number_service_workers_per_mode and len(tmp_list) > 0:
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

                    dist_list = []
                    for i, value_i in hexagons.items():
                        for j, value_j in hexagons.items():
                            if i != j:
                                dist_list.append((value_i, value_j, self._distance_matrix.loc[j][i]))

                    # Initialize fitness function object using dist_list
                    fitness_dists = mlrose.TravellingSales(distances=dist_list)

                    # Define optimization problem object
                    problem_fit = mlrose.TSPOpt(length=len(hexagons), fitness_fn=fitness_dists, maximize=False)

                    # Solve problem using the genetic algorithm (keep random state constant)
                    best_state, best_fitness = mlrose.genetic_alg(problem_fit, random_state=1337)

                    # Convert Numpy Array to List
                    best_state = best_state.tolist()

                    # Shift list
                    index_of_destination = best_state.index(0)

                    # Position "Destination" of relocations to the end
                    if len(best_state)-1 != index_of_destination:
                        best_state = best_state[index_of_destination+1:] + best_state[:index_of_destination+1]

                    # We start at the origin and end at the destination. Distance between "destination" and "origin"
                    # must be substracted from the best fit.
                    origin_of_trip = best_state[0]
                    dest_of_trip   = best_state[-1]

                    excess_distance = 0
                    for distance_weights in dist_list:
                        # distance_weights[0] => origin, distance_weights[1] => destination
                        # In our case dest_of_trip refers to the "origin" and origin_of_trip to "destination"
                        # <=> remove last edge from the route
                        if distance_weights[0] == dest_of_trip and distance_weights[1] == origin_of_trip:
                            excess_distance += distance_weights[2]

                    # Remove the distance from the "destination" to the "origin" of the relocation trip
                    total_distance = best_fitness - excess_distance

                    average_distance_per_relocation_step = total_distance/len(relocation)

                    # Save old tuples
                    old_relocation = relocation.copy()

                    # Remove old tuples
                    relocation.clear()

                    # Override distances based on calculated traveling salesman problem solution
                    for elem in old_relocation:
                        tmp_elem = list(elem)
                        tmp_elem[3] = average_distance_per_relocation_step
                        tmp_elem = (*tmp_elem, )

                        relocation.append(tmp_elem)

        return relocations


    def calculate_resource_capacity_split_for_relocation(self, fleet_state, available_vehicle_modes, max_vehicle_supply, number_service_workers_per_mode):
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
            current_supply_mismatch.append(fleet_state[f"Residual_Supply_{mode}"].abs().sum() / max_capacity_per_unit)

            max_unit_assignment.append(round(max_vehicle_supply[idx]/max_capacity_per_unit+0.49)) # Round Up

        # Normalize by number of vehicles
        current_supply_mismatch = [supply_mismatch / max_supply for supply_mismatch, max_supply in
                                 zip(current_supply_mismatch, max_vehicle_supply)]

        # Temporary Denom
        denominator = sum(current_supply_mismatch)

        if denominator == 0.0:
            # No Relocations Needed => No Workers assigned
            return len(current_supply_mismatch)*[0]

        # Split capacity based on the following fraction
        capacity_fraction = current_supply_mismatch / denominator

        capacity = capacity_fraction * number_service_workers_per_mode

        capacity = [round(x) for x in capacity]

        capacity = [min(capa, max_unit_assign) for capa, max_unit_assign in zip(capacity, max_unit_assignment)]

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

    def calculate_residual_supply(self, vehicle_fleet, transactions):
        """
        Calculate Relocation Strategy based on (Expected) Demand, Supply and Vehicles to be Charged
        :param vehicle_fleet: (Mixed) Vehicle Fleet
        :param transactions: Transaction record from @PaymentInterface
        :return:
        """

        # Get Vehicle Supply per Hexagon
        supply = vehicle_fleet.calc_supply_per_region()

        supply_df = pd.DataFrame(supply).T.reset_index()
        supply_df.rename(columns={"index": "hex_id"}, inplace=True)

        # Get LoW Soc Vehicle Supply per Hexagon
        low_soc_supply = vehicle_fleet.calc_vehicles_to_be_charged_per_region(0.1)

        df_low_soc = pd.DataFrame(low_soc_supply).T.reset_index()
        df_low_soc.rename(columns={"index": "hex_id"}, inplace=True)

        # Get Expected Demand (Delta) per Hexagon
        expected_demand = self.estimate_delta_demand(transactions, self._available_vehicle_modes)

        # Merge Demand, Suppy and Low SoC Vehicles
        state = expected_demand.merge(supply_df, how = "outer", on = "hex_id")
        state = state.merge(df_low_soc, how = "outer", on = "hex_id", suffixes = ("", "_Low_SoC"))
        state.fillna(0, inplace=True)

        # Calculate Residual Supply for each vehicle type
        # RS = Supply - Low SoC Vehicles - Delta Demand (i.e., E[Inflow]-E[Outflow]-E[Missed Trips]
        for vehicle in self._available_vehicle_modes:
            # + Delta because delta is negative or positive based on calc delta demand
            state[f"Residual_Supply_{vehicle}"] = state[vehicle] - state[f"{vehicle}_Low_SoC"] + state[f"Delta_{vehicle}"]

        return state

    def estimate_delta_demand(self, transactions, ordered_available_vehicle):
        """
            Compute the expected demand in a hexagon based on collected rental transactions from the simulation.

            Transactions: Transaction Records from the Payment Interface
            Ordered_Available_Vehicle: List with Available Vehicles and Natural Ordering of Preference in case of neutrality
                i.e., the following hodls
                    ordered_available_vehicle[i] = 1 and ordered_available_vehicle[k] = 1

                                            k > i

                    =>

                    Demand is counted for: ordered_available_vehicle[i] as we assume preference order i << k

            We calculate for each vehicle type -- based on the previous assumption -- the delta demand:

                    E[Delta Demand| Hexagon ID] = E[Inflow | Hexagon ID] - E[Outflow s| Hexagon ID] - E[Missed Trips | Hexagon ID]
        """
        transactions  = transactions.copy()

        diff = set(transactions["selected_vehicle_mode"].unique()) - set(ordered_available_vehicle + ['None'])

        if len(diff) > 0:
           raise RuntimeError('There are more vehicle types than defined in ordered available vehicle')

        if len(set(transactions["selected_vehicle_mode"].unique())) == 1:
           raise RuntimeError('There are not enough transactions to calculate historical values')

        # Rearrange Columns according to Vehicle Preferences
        cols = transactions.columns.tolist()
        cols = cols[:-(len(ordered_available_vehicle))] + ordered_available_vehicle

        # Rearrange Columns
        transactions = transactions[cols]

        # Get the cheapest (most-preferred) mode for that trip.
        # In other words, if a trip can be undertaken either by scooter or car, count this as a scooter trip
        transactions["cheapest_vehicle_mode"] = ''

        for i in range(len(ordered_available_vehicle)):
            query = '{} == {}'.format(ordered_available_vehicle[i], 1)
            for k in range(i):
                query += ' & {} == {}'.format(ordered_available_vehicle[k], 0)

            qry_res = transactions.query(query) # If not empty
            if qry_res.shape[0] > 0:
                transactions.loc[qry_res.index, "cheapest_vehicle_mode"] = ordered_available_vehicle[i]

        # (All) Hexagons
        hexagons = pd.unique(transactions[["origin", "destination"]].values.ravel('K'))
        hexagons = pd.DataFrame(hexagons, columns=["hex_id"])

        # Calculate Expected Outflow
        outflow = transactions.groupby(["origin", "state", "cheapest_vehicle_mode"]).agg({"destination": "count"})

        # Unstack Vehicle Type Level
        outflow = outflow.unstack()
        vehicle_columns = list(outflow["destination"].columns.values)
        # Reset Multi-Index to Flat Index
        outflow = outflow.reset_index()
        outflow.columns = ["origin", "state"] + vehicle_columns

        # to ensure that "fulfilled" comes before "missed" during unstacking
        outflow = outflow.sort_values(["origin", "state"])

        # Unstack State Column
        outflow = outflow.set_index(["origin", "state"])
        outflow = outflow.unstack().reset_index()

        # Arrange Column Names
        unfolded_cols = ["hex_id"]
        for vehicle in vehicle_columns:
            unfolded_cols = unfolded_cols + ["OutFlow_Fulfilled_{}".format(vehicle), "OutFlow_Missed_{}".format(vehicle)]

        # Overwrite Column Names
        outflow.columns = unfolded_cols

        # Calculate Expected Inflow
        inflow = transactions.groupby(["destination", "state", "cheapest_vehicle_mode"]).agg({"origin": "count"})

        # Unstack Vehicle Type Level
        inflow = inflow.unstack()
        base_column = ["destination", "state"]
        vehicle_columns = list(inflow["origin"].columns.values)

        # Reset Multi-Index to Flat Index (keep vehicle column order)
        inflow = inflow.reset_index()
        inflow.columns = ["hex_id", "state"] + ["Inflow_{}".format(vehicle) for vehicle in vehicle_columns]

        # to ensure that "fulfilled" comes before "missed" during unstacking
        inflow = inflow.sort_values(["hex_id", "state"])

        # Inflow, we just need fulfilled trips to estimate expected inflow
        inflow = inflow[inflow["state"] == "Fulfilled"]
        inflow = inflow.drop(columns={"state"})
        inflow = inflow.reset_index()
        inflow.drop(columns={"index"}, inplace=True)

        # Put together expected outflow and inflow
        result = hexagons.merge(inflow, on=["hex_id"], how="left", suffixes=("", ""))
        result = result.merge(outflow, on=["hex_id"], how="left", suffixes=("_inflow", "_outflow"))
        result.fillna(0, inplace=True)

        # Calculate Delta (Expected Inflow - Expected Outflow - Missed Demand)
        for vehicle in ordered_available_vehicle:
            result["Delta_{}".format(vehicle)] = result["Inflow_{}".format(vehicle)] - result[
                "OutFlow_Fulfilled_{}".format(vehicle)] - result["OutFlow_Missed_{}".format(vehicle)]

        return result