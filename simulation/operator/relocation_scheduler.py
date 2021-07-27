import pandas as pd


class RelocationScheduler:

    def __init__(self):
        print("X")


    def compute_relocations(self, vehicle_fleet, transactions):
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
        expected_demand = self.estimate_delta_demand(transactions)

        # Merge Demand, Suppy and Low SoC Vehicles
        state = expected_demand.merge(supply_df, how = "outer", on = "hex_id")
        state = state.merge(df_low_soc, how = "outer", on = "hex_id", suffixes = ("", "_Low_SoC"))
        state.fillna(0, inplace=True)

        # Calculate Residual Supply for each vehicle type
        # RS = Supply - Low SoC Vehicles - Delta Demand (i.e., E[Inflow]-E[Outflow]-E[Missed Trips]
        for vehicle in ["SharedKickScooter", "SharedScooter", "SharedCar"]:
            # + Delta because delta is negative or positive based on calc delta demand
            state[f"Residual_Supply_{vehicle}"] = state[vehicle] - state[f"{vehicle}_Low_SoC"] + state[f"Delta_{vehicle}"]

        return state

    def estimate_delta_demand(self, transactions, ordered_available_vehicle=["SharedKickScooter", "SharedScooter", "SharedCar"]):
        """
            Compute the expected demand in a hexagon based on collected rentral transactions from the simulation.

            Transactions: Transaction Records from the Payment Interface
            Ordered_Available_Vehicle: List with Available Vehicles and Natural Ordering of Preference in case of neutrality
                i.e., the following hodls
                    ordered_available_vehicle[i] = 1 and ordered_available_vehicle[k] = 1

                                            k > i

                    =>

                    Demand is counted for: ordered_available_vehicle[i] as we assume preference order i << k

            We calculate for each vehicle type -- based on the previous assumtion -- the delta demand:

                    E[Delta Demand| Hexagon ID] = E[Inflow | Hexagon ID] - E[Outflow s| Hexagon ID] - E[Missed Trips | Hexagon ID]
        """
        transactions  = transactions.copy()
        # diff = set(transactions["selected_vehicle_mode"].unique() + ['None']) - set(ordered_available_vehicle)

        # if len(diff) > 0:
        #    raise RuntimeError('There are more vehicle types than defined in ordered available vehicle')

        # Rearrange Columns according to Vehicle Preferences
        cols = transactions.columns.tolist()
        cols = cols[:-(len(ordered_available_vehicle))] + ordered_available_vehicle
        cols

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