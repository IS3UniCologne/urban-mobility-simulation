import logging
from typing import Dict, List

import numpy as np
import pandas as pd
from docplex.mp.model import Model

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

# from Fleet_sim.location import closest_facility
# from Fleet_sim.log import lg


class DowntimeMinWithoutLookahead:
    __slots__ = ("_config", "_av_config")

    def __init__(self) -> None:
        self._config = Configuration()
        self._av_config = self._config.ride_hailing_vehicles["AutonomousCar"]

    def generate_charging_allocation(
        self, vehicles, CSs
    ) -> List[Dict[RideHailingVehicle, VirtualChargingStation]]:
        """
        This is a function of allocating charging vehicles to stations, using minimum downtime, only looking at the current situation, without pre-planning the future

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
                if i.capacity < 0:
                    raise ValueError("Capacity of CS must be positive")
                CSs_range.append(i.id)

            d = {}  # distance matrix
            # TODO: use haversine vector or distance matrix
            for j in vehicles:
                for i in CSs:
                    d[i.id, j.id] = i.centre >> j.position
                    # if isinstance(d[i.id, j.id], list):
                    #     d[i.id, j.id] = float([i.id, j.id][0])

            Q = {}  # queueing time of the CS
            N = {}  # available capacity (excl queue)
            M = {}  # available capacity (incl queue)
            C = {}  # total capacity of the CS
            for i in CSs:
                Q[i.id] = i.current_queue_time
                N[i.id] = i.capacity  # this only works with VirtualChargingStations !!
                # TODO: M should incorporate overflow of capa
                M[i.id] = i.capacity + (i.queue_size - len(i.plugs.queue))
                C[i.id] = i.plugs.capacity

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
                self._av_config.ENERGY_CONSUMPTION
            )  # charging consumption per distance in kWh/km
            beta = self._av_config.MAX_STATE_OF_CHARGE  # max state of charge in kWh
            rho = (
                self._config.ride_hailing_global.LOW_SOC_PENALTY
            )  # penalty for not allocating vehicles to CSs, scaled by 1 - SOC

            # x : main allocation variable; x_ij: if CS i is assigned to vehicle j
            x = mdl.binary_var_matrix(CSs_range, vehicle_range, name="x")

            # energy feasibility constraint
            for j in vehicles:
                for i in CSs:
                    mdl.add_constraint(
                        x[i.id, j.id] * d[i.id, j.id] / 1000 * alpha
                        <= SoC[j.id] * beta,
                        "C1",
                    )

            # capacity contraint
            for i in CSs:
                mdl.add_constraint(
                    mdl.sum(x[i.id, j.id] for j in vehicles) <= M[i.id], "C2"
                )
            T_d = {}  # driving time in min
            T_c = {}  # charging time in min
            T_q = {}  # queueing time in min

            # id_map = {i: v.id for i, v in enumerate(vehicles)}
            id_reverse_map = {v.id: i for i, v in enumerate(vehicles)}

            d_matrix = np.zeros((len(CSs), len(vehicles)))
            for i in CSs:
                for j in vehicles:
                    d_matrix[i.id][id_reverse_map[j.id]] = d[i.id, j.id]

            # this is a matrix of dim [CSs, vehicles] sorted by ascending distance of vehicles to CS, the values being the vehicles indices
            d_matrix_asc_sorted = np.argsort(d_matrix, axis=1)

            # # we can get the number of vehicles arriving before every vehicle at each charging station
            # vehicles_arriving_before = {}
            # for i in CSs:
            #     for j in vehicles:
            #         vehicles_arriving_before[i.id, j.id] = np.where(
            #             d_matrix_asc_sorted[i.id] == id_reverse_map[j.id]
            #         )[0][0]

            for i in CSs:
                for j in vehicles:
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

            # charging time of vehicles arriving before every vehicle at each charging station
            # this divided by the number of plugs at a CS is our best guess for additional queue time due to the allocation x
            # if capacity is free, then we need to exclude the first N[i.id] vehicles from that calculation as they will immediately charge without going to queue
            charging_time_faster_vehicles = {}
            for i in CSs:
                for j in vehicles:
                    charging_time_faster_vehicles[i.id, j.id] = mdl.sum(
                        T_c[i.id, v.id]
                        for v in vehicles
                        if id_reverse_map[v.id]
                        in d_matrix_asc_sorted[i.id][
                            N[i.id] : np.where(
                                d_matrix_asc_sorted[i.id] == id_reverse_map[j.id]
                            )[0][0]
                        ]
                    )

            for j in vehicles:
                for i in CSs:
                    T_d[i.id, j.id] = (
                        d[i.id, j.id] / self._av_config.VELOCITY * x[i.id, j.id]
                    )

                    # the queueing time will vary based on how many vehicles are send there, we need to take this into account
                    # because exact solution approaches are intractible in realtime scenarios, we use approximation for how long one other assignment would potentially increase our queueing time
                    T_q[i.id, j.id] = mdl.max(0, Q[i.id] - T_d[i.id, j.id]) + (
                        charging_time_faster_vehicles[i.id, j.id] / i.plugs.capacity
                    )

            # assign each vehicle at max to one CS
            for j in vehicles:
                mdl.add_constraint(mdl.sum(x[i.id, j.id] for i in CSs) <= 1)

            # minimizing sum of (driving_time + queue_time + charging_time) for all vehicles + a high penalty to missed demands
            # we enforce priority of low SOC vehicles by scaling a penalty of cumulated distance sum

            mdl.minimize(
                mdl.sum(
                    T_d[i.id, j.id]  # driving time
                    + T_c[i.id, j.id]  # charging time
                    + T_q[i.id, j.id]  # queuing time
                    for i in CSs
                    for j in vehicles
                )
                + mdl.sum(
                    (1 - SoC[j.id])  # 1-SOC of vehicle j
                    * rho  # large number O_O
                    * (
                        1 - mdl.sum(x[i.id, j.id] for i in CSs)
                    )  # allocation (0) or not (1) of vehicle j to any charging station i
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
            T_q_sum = mdl.sum(
                T_q[i.id, j.id] for i in CSs for j in vehicles
            ).solution_value

            logging.debug(
                f"T_d = {T_d_sum}, T_c = {T_c_sum}, T_q = {T_q_sum}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            logging.debug(
                f"Penalty for not charging vehicles = {mdl.sum(mdl.sum(d[i.id, j.id] for i in CSs) * (1 - SoC[j.id]) * (1 - mdl.sum(x[i.id, j.id] for i in CSs)) for j in vehicles).solution_value}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

            stats_allocations = (
                pd.Series(
                    [
                        v.current_relative_state_of_charge
                        for i in pairs
                        for k, v in i.items()
                        if k == "vehicle"
                    ]
                )
                .describe()
                .__str__()
                .split("\n")
            )
            logging.debug(
                f"Stats of allocations: {stats_allocations}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            stats_candidates = (
                pd.Series([v.current_relative_state_of_charge for v in vehicles])
                .describe()
                .__str__()
                .split("\n")
            )
            logging.debug(
                f"Stats of candidates: {stats_candidates}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
        return pairs
