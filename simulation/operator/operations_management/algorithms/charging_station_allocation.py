import numpy as np  # noqa: D100
import pandas as pd
from pyomo.environ import (
    Binary,
    ConcreteModel,
    Constraint,
    NonNegativeReals,
    Objective,
    Set,
    SolverFactory,
    Var,
    minimize,
    value,
)

from simulation.context.simulation_context import SimulationContext
from simulation.helper.simulation_base import SimulationBase
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class DowntimeMinWithoutLookahead(SimulationBase):  # noqa: D101
    __slots__ = ("_operator",)

    def __init__(self, sim: SimulationContext, operator: RideHailingOperator) -> None:
        super().__init__(sim)
        self._operator = operator

    def generate_charging_allocation(
        self, vehicles: list[RideHailingVehicle], CSs: list[VirtualChargingStation]
    ) -> list[dict[RideHailingVehicle, VirtualChargingStation]]:
        """Allocate vehicles to charging stations.

        This is a function of allocating charging vehicles to stations, using minimum downtime, only looking at the current situation, without pre-planning the future.

        :param vehicles: a list of vehicle objects that need to charge
        :param CSs: a list of charging stations
        :return: pair of matched CSs and vehicles
        """
        mdl = ConcreteModel()
        vehicle_range = []
        for j in vehicles:
            vehicle_range.append(j.id)
        CSs_range = []

        for i in CSs:
            if i.capacity < 0:
                raise ValueError("Capacity of CS must be positive")
            CSs_range.append(i.cs_id)

        d = {}  # distance matrix
        for j in vehicles:
            for i in CSs:
                d[i.cs_id, j.id] = i.centre << j.position

        Q = {}  # queueing time of the CS
        N = {}  # available capacity (excl queue)
        M = {}  # available capacity (incl queue)
        C = {}  # total capacity of the CS
        for i in CSs:
            Q[i.cs_id] = i.current_queue_time
            N[i.cs_id] = i.capacity  # this only works with VirtualChargingStations !!
            M[i.cs_id] = (
                i.capacity - i.blocked_capacity + (i.queue_size - len(i.plugs.queue))
            )
            C[i.cs_id] = i.plugs.capacity

        SoC = {}  # state of charge for vehicles that need to charge
        for j in vehicles:
            SoC[j.id] = j.energy_system.current_energy_relative
            # if isinstance(SoC[j.id], list):
            #     SoC[j.id] = float(SoC[j.id][0])

        S = {}  # charging speed of stations in kW
        for i in CSs:
            S[i.cs_id] = i.power
            # if isinstance(S[i.id], list):
            #     S[i.id] = float(S[i.id][0])

        # TODO: This is under the assumption that all vehicles have the same consumption and battery capacity
        # charging consumption per distance in kWh/km
        alpha = vehicles[0].energy_system.energy_consumption_per_km
        # max state of charge in kWh
        beta = vehicles[0].energy_system.capacity
        rho = self._operator.operations.config.LOW_SOC_PENALTY

        mdl.CSs = Set(initialize=CSs_range)
        mdl.vehicles = Set(initialize=vehicle_range)

        # x : main allocation variable; x_ij: if CS i is assigned to vehicle j
        mdl.x = Var(mdl.CSs, mdl.vehicles, within=Binary, name="x")

        # energy feasibility constraint
        def energy_feasibility_rule(model, i, j):  # noqa: ANN001, ANN202
            return model.x[i, j] * d[i, j] / 1000 * alpha <= SoC[j] * beta

        mdl.energy_feasibility = Constraint(
            mdl.CSs, mdl.vehicles, rule=energy_feasibility_rule
        )

        # capacity contraint
        def capacity_constraint_rule(model, i):  # noqa: ANN001, ANN202
            return sum(model.x[i, j] for j in model.vehicles) <= M[i]

        mdl.capacity_constraint = Constraint(mdl.CSs, rule=capacity_constraint_rule)

        id_reverse_map = {v.id: i for i, v in enumerate(vehicles)}

        d_matrix = np.zeros((len(CSs), len(vehicles)))
        for i in CSs:
            for j in vehicles:
                d_matrix[i.cs_id][id_reverse_map[j.id]] = d[i.cs_id, j.id]

        # this is a matrix of dim [CSs, vehicles] sorted by ascending distance of vehicles to CS, the values being the vehicles indices
        d_matrix_asc_sorted = np.argsort(d_matrix, axis=1)

        vehicle_index_in_sorted_dist_matrix = {}
        for i in CSs:
            for j in vehicles:
                vehicle_index_in_sorted_dist_matrix[i.cs_id, j.id] = np.where(
                    d_matrix_asc_sorted[i.cs_id] == id_reverse_map[j.id]
                )[0][0]

        # assign each vehicle at max to one CS
        def max_one_cs_per_vehicle_rule(model, j):  # noqa: ANN001, ANN202
            return sum(model.x[i, j] for i in model.CSs) <= 1

        mdl.max_one_cs_per_vehicle = Constraint(
            mdl.vehicles, rule=max_one_cs_per_vehicle_rule
        )

        mdl.queueing_time_aux = Var(mdl.CSs, mdl.vehicles, within=NonNegativeReals)

        def driving_time(model: ConcreteModel, i: int, j: int) -> float:
            return d[i, j] / vehicles[0].velocity * model.x[i, j]

        def charging_time(model: ConcreteModel, i: int, j: int) -> float:
            A = 1 - SoC[j]
            B = d[i, j] / 1000 * alpha / beta
            C = beta / S[i] * 60
            return (A * C + B * C) * model.x[i, j]

        def queueing_time(model: ConcreteModel, i: int, j: int) -> float:
            return model.queueing_time_aux[i, j] + (
                sum(
                    charging_time(model, i, v.id)
                    for v in vehicles
                    if id_reverse_map[v.id]
                    in d_matrix_asc_sorted[
                        i, N[i] : vehicle_index_in_sorted_dist_matrix[i, j]
                    ]
                )
                / C[i]
            )

        def queueing_time_aux_rule1(model, i, j):  # noqa: ANN001, ANN202
            return model.queueing_time_aux[i, j] >= 0

        mdl.queueing_time_aux_constraint1 = Constraint(
            mdl.CSs, mdl.vehicles, rule=queueing_time_aux_rule1
        )

        def queueing_time_aux_rule2(model, i, j):  # noqa: ANN001, ANN202
            return model.queueing_time_aux[i, j] >= Q[i] - driving_time(model, i, j)

        mdl.queueing_time_aux_constraint2 = Constraint(
            mdl.CSs, mdl.vehicles, rule=queueing_time_aux_rule2
        )

        # minimizing sum of (driving_time + queue_time + charging_time) for all vehicles + a high penalty to missed demands
        # we enforce priority of low SOC vehicles by scaling a penalty of cumulated distance sum
        def objective_rule(model):  # noqa: ANN001, ANN202
            return sum(
                driving_time(model, i, j)
                + charging_time(model, i, j)
                + queueing_time(model, i, j)
                for i in model.CSs
                for j in model.vehicles
            ) + sum(
                (1 - SoC[j])  # 1-SOC of vehicle j
                * rho  # large number O_O
                * (
                    1 - sum(model.x[i, j] for i in model.CSs)
                )  # allocation (0) or not (1) of vehicle j to any charging station i
                for j in model.vehicles
            )

        mdl.objective = Objective(rule=objective_rule, sense=minimize)

        opt = SolverFactory("highs")
        try:
            opt.solve(mdl)
        except Exception as e:
            raise e

        pairs = []
        for i in CSs:
            for j in vehicles:
                if value(mdl.x[i.cs_id, j.id]) != 0:
                    pairs.append(dict(vehicle=j, charging_station=i))
        self.logger.info(
            "Number of vehicles with low SOC = %d, Number of allocations = %d",
            len(vehicles),
            len(pairs),
        )
        self.logger.debug("Objective value = %f", value(mdl.objective))

        stats_allocations = (
            pd.Series(
                [
                    v.energy_system.current_energy_relative
                    for i in pairs
                    for k, v in i.items()
                    if k == "vehicle"
                ]
            )
            .describe()
            .__str__()
            .split("\n")
        )
        self.logger.debug("Stats of allocations: %s", stats_allocations)
        stats_candidates = (
            pd.Series([v.energy_system.current_energy_relative for v in vehicles])
            .describe()
            .__str__()
            .split("\n")
        )
        self.logger.debug("Stats of candidates: %s", stats_candidates)

        return pairs
