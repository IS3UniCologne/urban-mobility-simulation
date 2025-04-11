import random
from datetime import datetime

import numpy as np
import pandas as pd
from docplex.mp.model import Model


def planning():
    start_time = datetime.now()
    random.seed(2)
    mdl = Model("Charging-cluster_Management")
    # mdl.parameters.timelimit = 7200 * 2
    data = pd.read_csv("weekday_time_bucket_4h_h3_start_7.csv")
    data = (
        data.groupby(["h3_start_7", "h3_end_7", "time_bucket_4h"])
        .agg({"total_trips": "mean"})
        .reset_index()
    )
    # mdl.parameters.mip.tolerances.mipgap = 0.01

    # Sets
    # space_range = data.h3_end_7.unique()
    # time_range = data.time_bucket_4h.unique()
    space_range = range(10)
    time_range = range(6)
    energy_range = range(5)

    # Parameters
    D_1 = {}
    D_2 = {}
    D_3 = {}
    TOU = {}
    ENERGY = {}
    for i in space_range:
        for j in space_range:
            TOU[i, j] = 1
            ENERGY[i, j] = 1
            for t in time_range:
                if i == j:
                    D_1[i, j, t] = D_2[i, j, t] = D_3[i, j, t] = 0
                else:
                    D_1[i, j, t] = D_2[i, j, t] = D_3[i, j, t] = np.random.randint(0, 2)

                """D_1[i, j, t] = data.loc[
                    (data['h3_start_7'] == i) & (data['h3_end_7'] == j) & (data['time_bucket_4h'] == t),
                    'total_trips'].values[0] * 0.05
                D_2[i, j, t] = data.loc[
                    (data['h3_start_7'] == i) & (data['h3_end_7'] == j) & (data['time_bucket_4h'] == t),
                    'total_trips'].values[0] * 0.025
                D_3[i, j, t] = data.loc[
                    (data['h3_start_7'] == i) & (data['h3_end_7'] == j) & (data['time_bucket_4h'] == t),
                    'total_trips'].values[0] * 0.025"""
    # Variables
    x_1 = mdl.integer_var_dict(
        (i, j, t, e)
        for i in space_range
        for j in space_range
        for t in time_range
        for e in energy_range
    )
    x_2 = mdl.integer_var_dict(
        (i, j, t, e)
        for i in space_range
        for j in space_range
        for t in time_range
        for e in energy_range
    )
    s_1 = mdl.integer_var_cube(space_range, time_range, energy_range, lb=0, name="s_1")
    s_2 = mdl.integer_var_cube(space_range, time_range, energy_range, lb=0, name="s_2")
    y_1 = mdl.integer_var_dict(space_range, lb=0, name="y_1")
    y_2 = mdl.integer_var_dict(space_range, lb=0, name="y_2")

    # Constraints
    for i in space_range:
        mdl.add_constraint(s_1[i, 0, 0] == y_1[i], "C1")
        mdl.add_constraint(s_2[i, 0, 0] == y_2[i], "C1")
        for t in time_range:
            for e in energy_range:
                mdl.add_constraint(
                    mdl.sum(x_1[i, j, t, e] for j in space_range) <= s_1[i, t, e], "C2"
                )
                mdl.add_constraint(
                    mdl.sum(x_2[i, j, t, e] for j in space_range) <= s_2[i, t, e], "C3"
                )
        for j in space_range:
            for t in time_range:
                mdl.add_constraint(
                    mdl.sum(x_1[i, j, t, e] for e in energy_range)
                    <= D_1[i, j, t] + D_3[i, j, t],
                    "C4",
                )
                mdl.add_constraint(
                    mdl.sum(x_2[i, j, t, e] for e in energy_range)
                    <= D_2[i, j, t] + D_3[i, j, t],
                    "C5",
                )
                mdl.add_constraint(
                    mdl.sum(x_1[i, j, t, e] for e in energy_range)
                    + mdl.sum(x_2[i, j, t, e] for e in energy_range)
                    <= D_1[i, j, t] + D_2[i, j, t] + D_3[i, j, t],
                    "C6",
                )
        for t in range(1, time_range[-1] + 1):
            mdl.add_constraint(
                s_1[i, t, 0]
                == s_1[i, t - 1, 0] - mdl.sum(x_1[i, j, t - 1, 0] for j in space_range),
                "C7",
            )
            mdl.add_constraint(
                s_2[i, t, 0]
                == s_2[i, t - 1, 0] - mdl.sum(x_2[i, j, t - 1, 0] for j in space_range),
                "C8",
            )
        for e in range(1, energy_range[-1] + 1):
            mdl.add_constraint(s_1[i, 0, e] == 0, "C1")
            mdl.add_constraint(s_2[i, 0, e] == 0, "C1")
            for t in range(1, time_range[-1] + 1):
                mdl.add_constraint(
                    s_1[i, t, e]
                    == s_1[i, t - 1, e]
                    + mdl.sum(x_1[j, i, t - 1, e - 1] for j in space_range)
                    - mdl.sum(x_1[i, j, t - 1, e] for j in space_range),
                    "C7",
                )
                mdl.add_constraint(
                    s_2[i, t, e]
                    == s_2[i, t - 1, e]
                    + mdl.sum(x_2[j, i, t - 1, e - 1] for j in space_range)
                    - mdl.sum(x_2[i, j, t - 1, e] for j in space_range),
                    "C8",
                )

    Revenue = mdl.sum(
        x_1[i, j, t, e] * 10 + x_2[i, j, t, e] * 4
        for i in space_range
        for j in space_range
        for t in time_range
        for e in energy_range
    )
    Costs = mdl.sum(y_1[i] * 29.86 + y_2[i] * 7.66 for i in space_range)
    mdl.maximize(Revenue - Costs)
    print("Start_time: {}".format(start_time))
    mdl.print_information()
    assert mdl.solve()
    mdl.report()

    for t in time_range:
        print(
            f"S_1_{t} = {mdl.sum(s_1[i, t, e] for e in energy_range for i in space_range).solution_value}"
        )
        print(
            f"S_2_{t} = {mdl.sum(s_2[i, t, e] for e in energy_range for i in space_range).solution_value}"
        )
    for i in space_range:
        if y_1[i].solution_value != 0:
            print(f"y_1_{i} = {y_1[i].solution_value}")
        if y_2[i].solution_value != 0:
            print(f"y_2_{i} = {y_2[i].solution_value}")
        for t in time_range:
            for e in energy_range:
                if s_1[i, t, e].solution_value != 0:
                    print(f"S_1_{i, t, e} = {s_1[i, t, e].solution_value}")

                if s_2[i, t, e].solution_value != 0:
                    print(f"S_2_{i, t, e} = {s_2[i, t, e].solution_value}")
                for j in space_range:
                    if x_1[i, j, t, e].solution_value != 0:
                        print(f"x_1_{i, j, t, e} = {x_1[i, j, t, e].solution_value}")
                    if x_2[i, j, t, e].solution_value != 0:
                        print(f"x_2_{i, j, t, e} = {x_2[i, j, t, e].solution_value}")
    print(
        f"x_{1} = {mdl.sum(x_1[i, j, t, e] for i in space_range for j in space_range for t in time_range for e in energy_range).solution_value}"
    )
    print(
        f"x_{2} = {mdl.sum(x_2[i, j, t, e] for i in space_range for j in space_range for t in time_range for e in energy_range).solution_value}"
    )
    """for i in space_range:
        for j in space_range:
            for t in time_range:
                if x_1[i, j, t].solution_value != 0:
                    print(f'x_1_{i, j, t} = {x_1[i, j, t].solution_value}')
                if x_2[i, j, t].solution_value != 0:
                    print(f'x_2_{i, j, t} = {x_2[i, j, t].solution_value}')"""

    """try:
        assert mdl.solve(), "!!! Solve of the model fails"
        end_time = datetime.now()
        lg.error('Duration: {}'.format(end_time - start_time))
        NoC = mdl.sum(x[k] for k in space_range)
        NoP = mdl.sum(y[k] for k in space_range)
        lg.error('c1: {}'.format(c1.solution_value))
        lg.error('c2: {}'.format(c2.solution_value))
        lg.error('pv: {}'.format(pv.solution_value))
        lg.error('b_size: {}'.format(b_size.solution_value))
        lg.error('NoC: {}'.format(NoC.solution_value))
        lg.error('NoP: {}'.format(NoP.solution_value))

        mdl.report()
        lg.error(f'facility = {facility}, date = {date}')
        lg.error(f'objective_function = {mdl.objective_value}')
        lg.error(f'p_plus = {p_plus.solution_value}')
        lg.error(f'p_star = {p_star.solution_value}')
        for k in space_range:
            if x[k].solution_value != 0:
                lg.error(f'x_{k} = {x[k].solution_value}')

            for k in space_range:
                if y[ k].solution_value != 0:
                    lg.error(f'y_{k} = {y [k].solution_value}')
6
        for j in vehicle_range:
            for k in space_range:
                for t in time_range:
                    if h[k, j, t].solution_value != 0:
                        lg.error(f'w_{k, j} = {w[k, j].solution_value}, '
                                 f'h_{k, j, t} = {h[k, j, t].solution_value}, '
                                 f'A_{j} = {A[j]}, D_{j} = {D[j]}, '
                                 f'e_{j} = {e_d[j]}')
        for k in time_range:
            if b_charge[k].solution_value != 0:
                lg.error(f'b_charge_{k} = {b_charge[k].solution_value}')
            if b_discharge[k].solution_value != 0:
                lg.error(f'b_discharge_{k} = {b_discharge[k].solution_value}')
            if SoC[k].solution_value != 0:
                lg.error(f'SoC_{k} = {SoC[k].solution_value}')

        v_index = pd.MultiIndex.from_product([space_range, vehicle_range, range(24)],
                                             names=['charger', 'vehicle', 'time'])
        v_results = pd.DataFrame(-np.random.rand(len(v_index), 5), index=v_index)
        v_results.columns = ['Energy', 'Connection', 'Arrival', 'Departure', 'Occupation']
        for j in vehicle_range:
            for k in space_range:
                for t in time_range:
                    v_results.loc[(k, j, t), 'Connection'] = w[k, j].solution_value
                    v_results.loc[(k, j, t), 'Energy'] = h[k, j, t].solution_value
                    v_results.loc[(k, j, t), 'Arrival'] = A[j]
                    v_results.loc[(k, j, t), 'Departure'] = D[j]
                    v_results.loc[(k, j, t), 'Occupation'] = w[k, j].solution_value * U[j, t]
        v_results.to_csv(f'vehicles_{facility}_{date}.csv')
        CS_index = pd.MultiIndex.from_product([space_range, connector_range],
                                              names=['charger', 'plug'])
        CS_results = pd.DataFrame(-np.random.rand(len(CS_index), 2), index=CS_index)
        CS_results.columns = ['CS', 'Connector']
        for k in space_range:
            CS_results.loc[(k, i), 'CS'] = x[k].solution_value
            CS_results.loc[(k, i), 'Connector'] = y[k].solution_value
        CS_results.to_csv(f'CS_{facility}_{date}.csv')

        results = pd.read_csv('results.csv')

        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'Installation_costs'] = c1.solution_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'Operations_costs'] = c2.solution_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'NoC'] = NoC.solution_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'NoP'] = NoP.solution_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'P_plus'] = p_plus.solution_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'P_star'] = p_star.solution_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'costs'] = mdl.objective_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'Event'] = dfs["EntryHour"].count()
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'PV'] = pv.solution_value
        results.loc[(results['Facility'] == int(facility[-1])) & (
                results['Date'] == date), 'Battery'] = b_size.solution_value
        results.to_csv('results.csv')

    except:
        lg.error('it did not solve')
        lg.error(f'facility = {facility}, date = {date}')
        end_time = datetime.now()
        lg.error('Duration: {}'.format(end_time - start_time))
        return"""


planning()
