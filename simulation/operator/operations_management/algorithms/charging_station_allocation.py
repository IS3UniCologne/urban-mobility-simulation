import logging
from typing import Dict, List

import numpy as np
from docplex.mp.model import Model

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.charging_station import ChargingStation
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

# from Fleet_sim.location import closest_facility
# from Fleet_sim.log import lg


class TimeMin:
    def __init__(self) -> None:
        self._config = Configuration.instance()
        self._av_config = self._config.get_ridehailing_vehicle_config("AutonomousCar")

    def generate_charging_allocation(
        self, vehicles, CSs
    ) -> List[Dict[RideHailingVehicle, ChargingStation]]:
        """
        This is a function of allocating charging vehicles to stations, using minimum downtime
        :param vehicles: a list of vehicle objects that need to charge
        :param CSs: a list of charging stations
        :return: pair of matched CSs and vehicles
        """
        with Model("charging_station_allocation") as mdl:
            vehicle_range = []
            for j in vehicles:
                vehicle_range.append(j.id)
            CSs_range = []

            for i in CSs:
                CSs_range.append(i.id)

            d = {}  # distance matrix
            # TODO: use haversine vector or distance matrix
            for j in vehicles:
                for i in CSs:
                    d[i.id, j.id] = i.centre >> j.position
                    # if isinstance(d[i.id, j.id], list):
                    #     d[i.id, j.id] = float([i.id, j.id][0])

            N = {}  # number of vehicles in the queue
            M = {}  # charging capacity + queue capacity (e.g., 10)
            C = {}  # charging capacity
            for i in CSs:
                N[i.id] = len(i.plugs.queue)
                if isinstance(N[i.id], list):
                    N[i.id] = float(N[i.id][0])
                M[i.id] = i.capacity + i.queue_size
                if isinstance(M[i.id], list):
                    M[i.id] = float(M[i.id][0])
                C[i.id] = i.capacity
                if isinstance(C[i.id], list):
                    C[i.id] = float(C[i.id][0])
            SoC = {}  # state of charge for vehicles that need to charge
            for j in vehicles:
                SoC[j.id] = j.current_relative_state_of_charge
                # if isinstance(SoC[j.id], list):
                #     SoC[j.id] = float(SoC[j.id][0])

            S = {}  # charging speed of stations in kW
            for i in CSs:
                S[i.id] = i.power
                # if isinstance(S[i.id], list):
                #     S[i.id] = float(S[i.id][0])
            alpha = (
                self._av_config.energy_consumption
            )  # charging consumption per distance in kWh/km
            beta = self._av_config.max_state_of_charge  # max state of charge in kWh
            rho = (
                self._config.ridehailing_operator_config.allocation_penalty
            )  # penalty for not allocating vehicles to CSs, scaled by 1 - SOC

            # x : main allocation variable; x_ij: if CS i is assigned to vehicle j
            x = mdl.binary_var_matrix(CSs_range, vehicle_range, name="x")
            # T_q: queue time at each station (helping variable)
            # T_q = mdl.continuous_var_dict(CSs_range, lb=0, name="T_q")

            # energy feasibility constraint
            for j in vehicles:
                for i in CSs:
                    mdl.add_constraint(
                        x[i.id, j.id] * d[i.id, j.id] / 1000 * alpha
                        <= SoC[j.id] * beta,
                        "C1",
                    )
            # capacity feasibility constraint
            for i in CSs:
                mdl.add_constraint(
                    N[i.id] + mdl.sum(x[i.id, j.id] for j in vehicles) <= M[i.id], "C2"
                )
            T_d = {}  # driving time in min
            T_c = {}  # charging time in min

            # TODO: for later versions we should use remaining charging times and charging demands of the current queue, for this we need to have a way to know the charging vehicles' estimated completion time, probably clever to do this in a service task and have the current executing task associated with every vehicle
            # vehicle.current_task.completion_time
            # for currently queueing vehicles,
            # for i in CSs:
            #     # 40 (kWh) is the expected average charging demand
            #     mdl.add_constraint(
            #         T_q[i.id]
            #         >= (N[i.id] + mdl.sum(x[i.id, j.id] for j in vehicles) - C[i.id])
            #         * 40
            #         / S[i.id]
            #     )

            # you can calculate the exact q time for vehicles in each charging station later (you need to calculate the priority though)
            for j in vehicles:
                for i in CSs:
                    T_d[i.id, j.id] = (
                        d[i.id, j.id] / self._av_config.velocity * x[i.id, j.id]
                    )
                    # for charging time we need to connsider the amount of SOC depleted while going to a station
                    T_c[i.id, j.id] = (
                        (
                            1
                            - SoC[j.id]
                            + (x[i.id, j.id] * d[i.id, j.id] / 1000 * alpha / beta)
                        )
                        * beta
                        / S[i.id]
                        * 60
                        * x[i.id, j.id]
                    )

            # assign each vehicle at max to one CS
            for j in vehicles:
                mdl.add_constraint(mdl.sum(x[i.id, j.id] for i in CSs) <= 1)

            # minimizing sum of (driving_time + queue_time + charging_time) for all vehicles + a high penalty to missed demands
            # you can move the penalty term to a constraint, but it gets infeasible if supply>demand
            # we enforce priority of low SOC vehicles by scaling a penalty of cumulated distance sum

            mdl.minimize(
                mdl.sum(
                    T_d[i.id, j.id] + T_c[i.id, j.id] for i in CSs for j in vehicles
                )
                + mdl.sum(
                    mdl.sum(d[i.id, j.id] for i in CSs)
                    * np.exp(1 - SoC[j.id])
                    * (1 - mdl.sum(x[i.id, j.id] for i in CSs))
                    for j in vehicles
                )
            )

            mdl.solve()

            pairs = []
            for i in CSs:
                for j in vehicles:
                    if x[i.id, j.id].solution_value != 0:
                        pairs.append(dict(vehicle=j, charging_station=i))
            logging.info(
                f"Number of vehicles with low SOC = {len(vehicles)}, Number of allocations = {len(pairs)}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            T_d_sum = mdl.sum(
                T_d[i.id, j.id] for i in CSs for j in vehicles
            ).solution_value
            T_c_sum = mdl.sum(
                T_c[i.id, j.id] for i in CSs for j in vehicles
            ).solution_value

            logging.debug(
                f"T_d = {T_d_sum}, T_c = {T_c_sum}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            logging.debug(
                f"Penalty for not charging vehicles = {mdl.sum( mdl.sum(d[i.id, j.id] for i in CSs) * (1 - SoC[j.id]) * (1 - mdl.sum(x[i.id, j.id] for i in CSs)) for j in vehicles )}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
        return pairs


# low energy, high priority
def charging_LE_HP(vehicles, q_vehicles, CSs):
    # try:
    mdl = Model("CS_development")
    # mdl.parameters.timelimit = 60
    vehicle_range = []
    for j in vehicles:
        vehicle_range.append(j.id)
    CSs_range = []
    ViQ = dict()
    for i in CSs:
        CSs_range.append(i.id)
        ViQ[i.id] = [v for v in q_vehicles if v.CS == i.id]

    d = {}
    for j in vehicles:
        for i in CSs:
            d[i.id, j.id] = i.location.distance_1(j.location)
            if isinstance(d[i.id, j.id], list):
                d[i.id, j.id] = float([i.id, j.id][0])

    priority = {}
    for j in vehicles:
        for i in vehicles:
            if j.charge_state < i.charge_state:
                priority[j.id, i.id] = 1
            else:
                priority[j.id, i.id] = 0
    N = {}
    M = {}
    C = {}
    for i in CSs:
        N[i.id] = len(i.plugs.queue)
        if isinstance(N[i.id], list):
            N[i.id] = float(N[i.id][0])
        M[i.id] = i.plugs.capacity + 10
        if isinstance(M[i.id], list):
            M[i.id] = float(M[i.id][0])
        C[i.id] = i.plugs.capacity
        if isinstance(C[i.id], list):
            C[i.id] = float(C[i.id][0])
    SoC = {}
    for j in vehicles:
        SoC[j.id] = j.charge_state
        if isinstance(SoC[j.id], list):
            SoC[j.id] = float(SoC[j.id][0])

    """SoCiQ = {}
    for i in CSs:
        for j in ViQ[i.id]:
            SoCiQ[i.id, j.id] = j.charge_state
            if isinstance(SoCiQ[i.id, j.id], list):
                SoCiQ[i.id, j.id] = float(SoCiQ[i.id, j.id][0])"""

    """p = {}
    for j in vehicles:
        for j_prime in vehicles:
            if SoC[j.id] > SoC[j_prime.id]:
                p[j.id, j_prime.id] = 1
            else:
                p[j.id, j_prime.id] = 0
    PiQ = {}
    for i in CSs:
        for j in vehicles:
            for j_prime in ViQ[i.id]:
                if SoC[j.id] > SoCiQ[i.id, j_prime.id]:
                    PiQ[i.id, j.id, j_prime.id] = 1
                else:
                    PiQ[i.id, j.id, j_prime.id] = 0"""

    S = {}
    for i in CSs:
        S[i.id] = i.power * 1
        if isinstance(S[i.id], list):
            S[i.id] = float(S[i.id][0])
    alpha = 0.2

    x = mdl.binary_var_matrix(CSs_range, vehicle_range, name="x")
    T_q = mdl.continuous_var_matrix(CSs_range, vehicle_range, lb=0, name="T_q")

    for j in vehicles:
        for i in CSs:
            mdl.add_constraint(x[i.id, j.id] * d[i.id, j.id] * alpha <= SoC[j.id], "C1")
    for i in CSs:
        mdl.add_constraint(
            N[i.id] + mdl.sum(x[i.id, j.id] for j in vehicles) <= M[i.id], "C2"
        )
    T_d = {}
    T_c = {}
    for i in CSs:
        for j in vehicles:
            mdl.add_constraint(
                T_q[i.id, j.id]
                >= (
                    N[i.id]
                    + mdl.sum(x[i.id, k.id] * priority[j.id, k.id] for k in vehicles)
                    - C[i.id]
                )
                / C[i.id]
                * 2
                * 40
                / S[i.id]
            )
            mdl.add_constraint(T_q[i.id, j.id] <= 1000 * x[i.id, j.id])
    for j in vehicles:
        for i in CSs:
            T_d[i.id, j.id] = d[i.id, j.id] / 0.05 * x[i.id, j.id]
            T_c[i.id, j.id] = (40 - SoC[j.id]) / S[i.id] * x[i.id, j.id]

    """for i in CSs:
        for j in vehicles:
            for j_prime in vehicles:
                mdl.add_constraint(2*y[i.id, j.id, j_prime.id] >= x[i.id, j.id] + x[i.id, j_prime.id], 'C3')"""

    for j in vehicles:
        mdl.add_constraint(mdl.sum(x[i.id, j.id] for i in CSs) <= 1)

    mdl.minimize(
        mdl.sum(
            T_d[i.id, j.id] + T_c[i.id, j.id] + T_q[i.id, j.id]
            for i in CSs
            for j in vehicles
        )
        + mdl.sum((1 - mdl.sum(x[i.id, j.id] for i in CSs)) for j in vehicles) * 10000
    )

    mdl.solve()
    # print(mdl.report())
    pairs = []
    for i in CSs:
        for j in vehicles:
            if x[i.id, j.id].solution_value != 0:
                pairs.append(dict(vehicle=j, charging_station=i))
    lg.info(f"Number of vehicles = {len(vehicles)}, Number of pairs = {len(pairs)}")
    T_d_sum = mdl.sum(T_d[i.id, j.id] for i in CSs for j in vehicles).solution_value
    T_c_sum = mdl.sum(T_c[i.id, j.id] for i in CSs for j in vehicles).solution_value
    T_q_sum = mdl.sum(T_q[i.id, j.id] for i in CSs for j in vehicles).solution_value
    lg.info(f"T_d = {T_d_sum}, T_c = {T_c_sum}, T_q = {T_q_sum}")
    """except:
        lg.info('Central charging fails')
        pairs = []
        for vehicle in vehicles:
            charging_station = closest_facility(CSs, vehicle)
            pairs.append(dict(vehicle=vehicle, charging_station=charging_station))
        lg.info(f'Number of vehicles = {len(vehicles)}, Number of pairs = {len(pairs)}')
    q = []
    for i in CSs:
        q.append(len(i.plugs.queue) + i.plugs.count)
    q = np.array(q)
    lg.info(f'queue = {q}')"""
    return pairs
