import logging
import sys
from pathlib import Path

import h3

# sys.modules["sklearn.externals.six"] = six
import mlrose as mlrose
import pandas as pd

from simulation.helper.configuration.configuration import Configuration


class RebalancingSchedulerRidehailing:
    def __init__(
        self,
        distance_matrix,
        fleet,
        ordered_available_vehicle_modes,
        ordered_max_vehicle_supply,
        number_of_service_units,
        base_regions,
        base_capacity,
        charging_threshold,
        charging_stations,
    ):
        # Distance Matrix between Regions
        self._distance_matrix = distance_matrix

        # Vehicle Fleet
        self._fleet = fleet

        # List needs to be ordered such that:
        # In case of neutral demand, we count the demand for the less expensive option
        # For example: If we observe a demand for KickScooter and Scooter, we count that
        # demand to KickScooter. This ordering is defined according to the following list
        # (from left to right)
        self._available_vehicle_modes = ordered_available_vehicle_modes
        self._max_vehicle_supply = ordered_max_vehicle_supply
        self._number_of_service_units = number_of_service_units
        self._base_regions = base_regions
        self._base_capacity = base_capacity
        self._charging_threshold = charging_threshold
        self._charging_stations = charging_stations

    def generate_relocation_plan(self, transactions):
        """

        Return relocation plan
        :param transactions: Simulation Transactions to calculate Fleet State and Expected In/Outlflows (from PaymentEngine)
        :return: Dict of potential relocations {"SharedCar": [(origin, destination, no, distance)], ..}
        """
        state = self.calculate_residual_supply(self._fleet, transactions)

        relocation_plans = self.identify_potential_relocations(state)

        return relocation_plans

    def generate_charging_plan(self):
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

        charging_plans = self.calculate_charging_plan(vehicles_to_charge)

        return charging_plans

    #############################################
    #############################################
    #  Charging Planing                         #
    #############################################
    #############################################

    def calculate_charging_plan(self, vehicles_to_charge):
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
                            x
                            for x in self._charging_stations
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
                    available_charging_stations = [x for x in self._charging_stations]
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
        capacity_per_mode = self.calculate_resource_capacity_split_for_relocation(
            state,
            self._available_vehicle_modes,
            self._max_vehicle_supply,
            self._number_of_service_units,
        )
        for i, mode in enumerate(self._available_vehicle_modes):
            # Relocation List containing tuples (origin, destination, number_of_vehicles_to_be_relocated, distance)
            relocation_list = []

            relocations[mode] = relocation_list

            # Get Max Charging Capacity per Service Worker Unit
            # e.g., 40 Kick Scooters by one SW, 1 Car by one SW
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Mode Specific Service Unit Resources (i.e., how many service workers have we assigned to collect the current mode)
            number_of_service_units_per_mode = capacity_per_mode[i]

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
                if len(relocation_list) == number_of_service_units_per_mode:
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
                        f"Cannot calculate relocation plan for {mode} as there are no regions with excess supply.",
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
                        and len(relocation_list) < number_of_service_units_per_mode
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

                    if len(relocation_list) == number_of_service_units_per_mode:
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
                    len(relocation_list) < number_of_service_units_per_mode
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

                    dist_list = []
                    for i, value_i in hexagons.items():
                        for j, value_j in hexagons.items():
                            if i != j:
                                dist_list.append(
                                    (value_i, value_j, self._distance_matrix.loc[j][i])
                                )

                    # Initialize fitness function object using dist_list
                    fitness_dists = mlrose.TravellingSales(distances=dist_list)

                    # Define optimization problem object
                    problem_fit = mlrose.TSPOpt(
                        length=len(hexagons), fitness_fn=fitness_dists, maximize=False
                    )

                    # Solve problem using the genetic algorithm (keep random state constant)
                    best_state, best_fitness = mlrose.genetic_alg(
                        problem_fit, random_state=1337
                    )

                    # Convert Numpy Array to List
                    best_state = best_state.tolist()

                    # Shift list
                    index_of_destination = best_state.index(0)

                    # Position "Destination" of relocations to the end
                    if len(best_state) - 1 != index_of_destination:
                        best_state = (
                            best_state[index_of_destination + 1 :]
                            + best_state[: index_of_destination + 1]
                        )

                    # We start at the origin and end at the destination. Distance between "destination" and "origin"
                    # must be substracted from the best fit.
                    origin_of_trip = best_state[0]
                    dest_of_trip = best_state[-1]

                    excess_distance = 0
                    for distance_weights in dist_list:
                        # distance_weights[0] => origin, distance_weights[1] => destination
                        # In our case dest_of_trip refers to the "origin" and origin_of_trip to "destination"
                        # <=> remove last edge from the route
                        if (
                            distance_weights[0] == dest_of_trip
                            and distance_weights[1] == origin_of_trip
                        ):
                            excess_distance += distance_weights[2]

                    # Remove the distance from the "destination" to the "origin" of the relocation trip
                    total_distance = best_fitness - excess_distance

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

    def calculate_resource_capacity_split_for_relocation(
        self,
        fleet_state,
        available_vehicle_modes,
        max_vehicle_supply,
        number_of_service_units,
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
            supply_mismatch / max_supply
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

        capacity = capacity_fraction * number_of_service_units

        capacity = [round(x) for x in capacity]

        capacity = [
            min(capa, max_unit_assign)
            for capa, max_unit_assign in zip(capacity, max_unit_assignment)
        ]

        # Rounding Fractions => Sum of Residual don't add up to available units
        # We fix this by adding or subtracting the residual to the max. element
        # Happens very rarely
        residual = number_of_service_units - sum(capacity)

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

    def calculate_low_soc_vehicles(self, vehicle_fleet):
        """
        Calculate Relocation Strategy based on (Expected) Demand, Supply and Vehicles to be Charged
        :param vehicle_fleet: (Mixed) Vehicle Fleet
        :param transactions: Transaction record from @PaymentInterface
        :return: List, vehicles with low state-of-charge
        """

        return vehicle_fleet.mark_vehicles_to_be_charged(self._charging_threshold)

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
        low_soc_supply = vehicle_fleet.calc_vehicles_to_be_charged_per_region(
            self._charging_threshold
        )

        df_low_soc = pd.DataFrame(low_soc_supply).T.reset_index()
        df_low_soc.rename(columns={"index": "hex_id"}, inplace=True)

        # Get Expected Demand (Delta) per Hexagon
        expected_demand = self.estimate_delta_demand(
            transactions, self._available_vehicle_modes
        )

        # Merge Demand, Suppy and Low SoC Vehicles
        state = expected_demand.merge(supply_df, how="outer", on="hex_id")
        state = state.merge(
            df_low_soc, how="outer", on="hex_id", suffixes=("", "_Low_SoC")
        )
        state.fillna(0, inplace=True)

        # Calculate Residual Supply for each vehicle type
        # RS = Supply - Low SoC Vehicles - Delta Demand (i.e., E[Inflow]-E[Outflow]-E[Missed Trips]
        for vehicle in self._available_vehicle_modes:
            # + Delta because delta is negative or positive based on calc delta demand
            state[f"Residual_Supply_{vehicle}"] = (
                state[vehicle] - state[f"{vehicle}_Low_SoC"] + state[f"Delta_{vehicle}"]
            )
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
        transactions = transactions.copy()

        diff = set(transactions["selected_vehicle_mode"].unique()) - set(
            ordered_available_vehicle + ["None"]
        )

        if len(diff) > 1:
            raise RuntimeError(
                "There are more vehicle types than defined in ordered available vehicle"
            )

        if len(set(transactions["selected_vehicle_mode"].unique())) == 1:
            raise RuntimeError(
                "There are not enough transactions to calculate historical values"
            )

        # Rearrange Columns according to Vehicle Preferences
        cols = transactions.columns.tolist()
        cols = cols[: -(len(ordered_available_vehicle))] + ordered_available_vehicle

        # Rearrange Columns
        transactions = transactions[cols]

        # Get the cheapest (most-preferred) mode for that trip.
        # In other words, if a trip can be undertaken either by scooter or car, count this as a scooter trip
        transactions["cheapest_vehicle_mode"] = ""

        for i in range(len(ordered_available_vehicle)):
            query = "{} == {}".format(ordered_available_vehicle[i], 1)
            for k in range(i):
                query += " & {} == {}".format(ordered_available_vehicle[k], 0)

            qry_res = transactions.query(query)  # If not empty
            if qry_res.shape[0] > 0:
                transactions.loc[
                    qry_res.index, "cheapest_vehicle_mode"
                ] = ordered_available_vehicle[i]

        # (All) Hexagons
        hexagons = pd.unique(transactions[["origin", "destination"]].values.ravel("K"))
        hexagons = pd.DataFrame(hexagons, columns=["hex_id"])

        # Calculate Expected Outflow
        outflow = transactions.groupby(
            ["origin", "state", "cheapest_vehicle_mode"]
        ).agg({"destination": "count"})

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
            unfolded_cols = unfolded_cols + [
                "OutFlow_Fulfilled_{}".format(vehicle),
                "OutFlow_Missed_{}".format(vehicle),
            ]

        # Overwrite Column Names
        outflow.columns = unfolded_cols

        # Calculate Expected Inflow
        inflow = transactions.groupby(
            ["destination", "state", "cheapest_vehicle_mode"]
        ).agg({"origin": "count"})

        # Unstack Vehicle Type Level
        inflow = inflow.unstack()
        ["destination", "state"]
        vehicle_columns = list(inflow["origin"].columns.values)

        # Reset Multi-Index to Flat Index (keep vehicle column order)
        inflow = inflow.reset_index()
        inflow.columns = ["hex_id", "state"] + [
            "Inflow_{}".format(vehicle) for vehicle in vehicle_columns
        ]

        # to ensure that "fulfilled" comes before "missed" during unstacking
        inflow = inflow.sort_values(["hex_id", "state"])

        # Inflow, we just need fulfilled trips to estimate expected inflow
        inflow = inflow[inflow["state"] == "Fulfilled"]
        inflow = inflow.drop(columns={"state"})
        inflow = inflow.reset_index()
        inflow.drop(columns={"index"}, inplace=True)

        # Put together expected outflow and inflow
        result = hexagons.merge(inflow, on=["hex_id"], how="left", suffixes=("", ""))
        result = result.merge(
            outflow, on=["hex_id"], how="left", suffixes=("_inflow", "_outflow")
        )
        result.fillna(0, inplace=True)

        # Calculate Delta (Expected Inflow - Expected Outflow - Missed Demand)
        for vehicle in ordered_available_vehicle:
            result["Delta_{}".format(vehicle)] = (
                result["Inflow_{}".format(vehicle)]
                - result["OutFlow_Fulfilled_{}".format(vehicle)]
                - result["OutFlow_Missed_{}".format(vehicle)]
            )

        return result
