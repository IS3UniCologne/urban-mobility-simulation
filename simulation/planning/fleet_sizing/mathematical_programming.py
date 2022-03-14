import random
from docplex.mp.model import Model
from datetime import datetime
import pandas as pd
import numpy as np

def planning():
    start_time = datetime.now()
    random.seed(2)
    mdl = Model("Charging-cluster_Management")
    # mdl.parameters.timelimit = 7200 * 2

    #mdl.parameters.mip.tolerances.mipgap = 0.01

    # Sets
    time = 1
    space_range = range(80)
    time_range = range(24)

    # Parameters
    D_1 = {}
    D_2 = {}
    D_3 = {}
    for i in space_range:
        for j in space_range:
            for t in time_range:
                D_1[i, j, t] = np.random.randint(10,40)
                D_2[i, j, t] = np.random.randint(10,40)
                D_3[i, j, t] = np.random.randint(10,40)

    # Variables
    x_1 = mdl.integer_var_cube(space_range, space_range, time_range, lb=0, name='x_1')
    x_2 = mdl.integer_var_cube(space_range, space_range, time_range, lb=0, name='x_2')
    s_1 = mdl.integer_var_matrix(space_range, time_range, lb=0, name='s_1')
    s_2 = mdl.integer_var_matrix(space_range, time_range, lb=0, name='s_2')
    y_1 = mdl.integer_var_dict(space_range, lb=0, name='y_1')
    y_2 = mdl.integer_var_dict(space_range, lb=0, name='y_2')

    # Constraints
    for i in space_range:
        mdl.add_constraint(s_1[i,0] == y_1[i], 'C1')
        mdl.add_constraint(s_2[i, 0] == y_2[i], 'C1')

        for t in time_range:
            mdl.add_constraint(mdl.sum(x_1[i,j,t] for j in space_range) <= s_1[i, t], 'C2')
            mdl.add_constraint(mdl.sum(x_2[i, j, t] for j in space_range) <= s_2[i, t], 'C3')
            mdl.add_constraint(mdl.sum(x_1[i, j, t] for j in space_range) <=
                               mdl.sum(D_1[i, j, t] for j in space_range) +
                               mdl.sum(D_3[i, j, t] for j in space_range), 'C4')
            mdl.add_constraint(mdl.sum(x_2[i, j, t] for j in space_range) <=
                               mdl.sum(D_2[i, j, t] for j in space_range) +
                               mdl.sum(D_3[i, j, t] for j in space_range), 'C5')
            mdl.add_constraint(mdl.sum(x_1[i, j, t] for j in space_range) +
                               mdl.sum(x_2[i, j, t] for j in space_range) <=
                               mdl.sum(D_1[i, j, t] for j in space_range) +
                               mdl.sum(D_2[i, j, t] for j in space_range) +
                               mdl.sum(D_3[i, j, t] for j in space_range), 'C6')
        for t in range(1,24):
            mdl.add_constraint(s_1[i,t] == s_1[i,t-1] + mdl.sum(x_1[j, i, t] for j in space_range) -
                               mdl.sum(x_1[i, j, t] for j in space_range), 'C3')

    Revenue = mdl.sum(x_1[i,j,t] + x_2[i,j,t] for i in space_range for j in space_range for t in time_range)
    Costs = mdl.sum(y_1[i] * 10 + y_2[i] * 10 for i in space_range)
    mdl.maximize(Revenue - Costs)
    print('Start_time: {}'.format(start_time))
    assert mdl.solve()
    mdl.report()

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
