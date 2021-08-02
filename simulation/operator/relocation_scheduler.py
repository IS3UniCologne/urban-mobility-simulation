from pathlib import Path

import pandas as pd

from simulation.helper.configuration.configuration import Configuration


class RelocationScheduler:

    def __init__(self, distance_matrix, fleet, available_vehicle_modes):
        # Distance Matrix between Regions
        self._distance_matrix = distance_matrix

        # Vehicle Fleet
        self._fleet = fleet

        # List needs to be ordered such that:
        # In case of neutral demand, we count the demand for the less expensive option
        # For example: If we observe a demand for KickScooter and Scooter, we count that
        # demand to KickScooter. This ordering is defined according to the following list
        # (from left to right)
        self._available_vehicle_modes = available_vehicle_modes

    def generate_relocation_plan(self, transactions, store_results = False):
        relocation_plan = self.calculate_residual_supply(self._fleet, transactions)

        config = Configuration.instance()
        if config.store_results:
            relocation_plan.to_csv(Path(config.output_path, config.fleet_state_file), index = False)

        # TODO: Collect firstly low soc vehicles and relocate to base, then charge,
        #  update relocation plan (more supply at base)
        # Implement function for pooled collection of vehicles, where the size of the pool is a parameter
        # For pooling, consider the nearest neighbours if vehicle has some space.

        relocation_plans = self.identify_potential_relocations(relocation_plan)

        return relocation_plans


    def identify_potential_relocations(self, relocation_plan):
        """
        Calculate how many vehicles need to be moved (or can be) from origin to destination
        :param relocation_plan: Output of function compute_relocations
        :return: Dictionary with relocation strategies for each vehicle mode under consideration
            - e.g., "SharedCar": [("origin", "destination", No_Vehicles_To_Move, Distance)]
        """
        relocations = {}
        for mode in self._available_vehicle_modes:
            # Relocation List containing tuples (origin, destination, number_of_vehicles_to_be_relocated, distance)
            relocation_list = []

            relocations[mode] = relocation_list

            # Already Relocated Vehicles
            hexagons = list(relocation_plan["hex_id"].unique())
            already_relocated = dict(zip(hexagons, [0] * len(hexagons)))

            for index, next_hex in relocation_plan[relocation_plan[f"Residual_Supply_{mode}"] < 0].iterrows():
                """
                  Iterate through each hexagon where we expect a negative supply (i.e., demand and supply don't match)
                """
                next_hex_id = next_hex["hex_id"]
                residual_supply = next_hex[f"Residual_Supply_{mode}"]

                # Already Relocated Vehicles into this Hexagon
                relocated_vehicles = 0

                # Get Distance To All Other Regions
                sub_distance_matrix = self._distance_matrix[[next_hex_id]].reset_index()
                sub_distance_matrix.rename(columns={"index": "hex_id"}, inplace=True)

                # Merge Sub Distance Matrix of selected Region with Relocation Plan
                # We obtain for the current hexagon a list of all hexagons along with their current vehicle supply
                distance_to_other_hexagons = sub_distance_matrix.merge(relocation_plan, how="inner", on="hex_id")

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
                    # Relocatable Vehicles = Additional Vehicles - Already (Planned) for Relocation Vehicles
                    relocatable_vehicles = row[f"Residual_Supply_{mode}"] - already_relocated[row["hex_id"]]
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

                # Append No. of Vehicles to be relocated
                distance_to_other_hexagons[f"Relocate_{mode}"] = pd.DataFrame(local_relocation_schedule, index=idx)

                for index, row in distance_to_other_hexagons[
                    distance_to_other_hexagons[f"Relocate_{mode}"] > 0].iterrows():
                    # List of (Origin, Destination, No. Vehicles to Relocate, Distance from Origin to Distance)
                    relocation_list.append((row["hex_id"], next_hex_id, row[f"Relocate_{mode}"], row[next_hex_id]))

        return relocations

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