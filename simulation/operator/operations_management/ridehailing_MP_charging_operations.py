from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

import pandas as pd
from simpy import AnyOf

from simulation.helper.configuration.configuration import (
    RideHailingMPChargingOperationsConfig,
)
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.ride_hailing_operations import (
    RideHailingOperations,
)
from simulation.operator.operations_management.service_tasks.charging_task_ridehailing import (
    ChargingTaskRidehailing,
)
from simulation.operator.operations_management.task_queue import TaskQueue

if TYPE_CHECKING:
    from simulation.operator.operations_management.operations import (
        OperationsDependencies,
    )


class RideHailingMPChargingOperations(RideHailingOperations):
    """
    Ridehailing Operations for Charging with Mathematical Programming / Optimization
    """  # noqa: D200, D400

    # TODO: Do we want to keep this in its current form as part of the core simulation?
    __slots__ = (
        "_algo",
        "_sim",
        "_state_of_charge_threshold",
        "_task_queue",
        "_task_transactions",
        "_time_between_operations",
        "_virtual_charging_infrastructure",
        "_world",
    )

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)

        self._sim = deps.sim
        self._world = deps.world
        self._time_between_operations = deps.operations_config.TIME_BETWEEN_OPERATIONS
        self._state_of_charge_threshold = deps.operations_config.RECHARGE_THRESHOLD

        ops_config = deps.operations_config
        if not isinstance(ops_config, RideHailingMPChargingOperationsConfig):
            raise TypeError(
                "RideHailingMPChargingOperations requires a "
                "RideHailingMPChargingOperationsConfig configuration."
            )

        self._algo = ops_config.CHARGING_ALGORITHM_TYPE(deps.sim, deps.operator)

        self._task_queue = TaskQueue(deps.sim)
        self._task_transactions = []

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None

    def execute(self) -> None:  # noqa: D102
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            sim=self._sim,
            charging_infrastructure=self.operator.charging_infrastructure,
            lookahead=None,
            use_virtual_cs=True,
        )

        #
        # at each time step the optimization needs to know the number of free slots in each charging station
        # because we send vehicles somewhere and while there on their way, execute operations again (maybe delay longer for this case?)
        # we should keep track of the expected number of free slots in each charging station
        # option a) track incoming vehicles seperately and sum up with current status
        # option b) track expected capacity incl incoming and outgoing and specific timesteps (like VirtualChargingInfrastructure?)
        #

        while True:
            yield self._env.timeout(self._time_between_operations)

            # Retrieve low SOC vehicles
            vehicles_to_charge = self.operator.fleet.mark_vehicles_to_be_charged(
                self._state_of_charge_threshold
            )
            if not vehicles_to_charge:
                continue

            # generate charging allocation using mathematical programming
            # list of pairs {vehicle: V, charging_station: C}
            allocations = self._algo.generate_charging_allocation(
                vehicles_to_charge,
                self._virtual_charging_infrastructure.charging_stations,
            )

            if not allocations:
                continue

            for charging_allocation in allocations:
                v = charging_allocation["vehicle"]
                c = charging_allocation["charging_station"]

                charging_task = ChargingTaskRidehailing(
                    sim=self._sim,
                    origin=v.position.get_region_id(),
                    destination=c.location,
                    number_of_vehicles_to_charge=1,
                    distance_to_fleet_base=None,
                    state_of_charge_threshold=self._state_of_charge_threshold,
                    charging_station=c,
                    vehicle=v,
                )

                # Schedule to Queue
                self._task_queue.append(charging_task)
                # Track task completion
                self._env.process(self._track_task(charging_task))

            while self._task_queue.count > 0:
                next_task = self._task_queue.popleft()
                self.logger.debug("Processing following task: %s.", next_task)
                self._env.process(next_task.execute())

                # Update virtual capacity when sending out a vehicle
                availability = (
                    self._virtual_charging_infrastructure.get_available_capacity()
                )
                availability[next_task.destination] -= 1
                self._virtual_charging_infrastructure.update(availability=availability)
                # and look out for when it arrives
                self._env.process(self._update_after_arrival(next_task))

    def _update_after_arrival(self, task):  # noqa: ANN001, ANN202
        # as soon as the vehicle really arrives, we can undo this because its then reflected in the capacity
        yield task._arrived_at_charging_station  # noqa: SLF001
        availability = self._virtual_charging_infrastructure.get_available_capacity()
        availability[task.destination] += 1
        self._virtual_charging_infrastructure.update(availability=availability)

    def _track_task(self, task):  # noqa: ANN001, ANN202
        yield AnyOf(self._env, [task.task_finished, self._world.simulation_finished])
        self._task_transactions.append(
            {
                "start_time": task._start_time,  # noqa: SLF001
                "estimated_arrival_time": task._estimated_arrival_time,  # noqa: SLF001
                "scheduled_time": task._scheduled_time,  # noqa: SLF001
                "end_time": self._env.now,
                "vehicle": task._vehicle.uid,  # noqa: SLF001
                "state": task.state,
                "fleet": task._vehicle.fleet.uid,  # noqa: SLF001
                "charging_station": task._charging_station.location,  # noqa: SLF001
                "waiting_time": task.waiting_time,
                "charging_duration": task.charging_duration,
                "estimated_completion_time": task._estimated_completion_time,  # noqa: SLF001
                "kWh_charged": task.kWh_charged,
            }
        )

    @property
    def task_transactions(self):  # noqa: ANN201, D102
        return pd.DataFrame(self._task_transactions)
