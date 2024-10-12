import logging

import pandas as pd
from simpy import AnyOf, Environment

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.service_tasks.charging_task_ridehailing import (
    ChargingTaskRidehailing,
)
from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.world.world import World


class RideHailingMPChargingOperations(OperationsInterface):
    """
    Ridehailing Operations for Charging with Mathematical Programming / Optimization
    """

    def __init__(
        self,
        env: Environment,
        time_between_operations: float,
        state_of_charge_threshold: float,
        algo=None,  # optimization problem
    ):
        super(RideHailingMPChargingOperations, self).__init__(env=env)

        self._world = None  # defer
        self._time_between_operations = time_between_operations
        self._state_of_charge_threshold = state_of_charge_threshold
        self._algo = algo

        self._task_queue = TaskQueue(env)
        self._task_transactions = []

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None

    def execute(self) -> None:
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            env=self._env,
            charging_infrastructure=self._operator_reference.charging_infrastructure,
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

        self._world = World.instance()

        while True:
            yield self._env.timeout(self._time_between_operations)

            # Retrieve low SOC vehicles
            vehicles_to_charge = (
                self._operator_reference.fleet.mark_vehicles_to_be_charged(
                    self._state_of_charge_threshold
                )
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
                    self._env,
                    origin=v.position.get_hexagon(return_geom=False)[0],
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
                logging.debug(
                    f"Processing following task: {next_task}.",
                    extra={
                        "clazz": self.__class__.__name__,
                        "oid": self._operator_reference.id,
                    },
                )
                self._env.process(next_task.execute())

                # Update virtual capacity when sending out a vehicle
                availability = (
                    self._virtual_charging_infrastructure.get_available_capacity()
                )
                availability[next_task.destination] -= 1
                self._virtual_charging_infrastructure.update(availability=availability)
                # and look out for when it arrives
                self._env.process(self._update_after_arrival(next_task))

    def _update_after_arrival(self, task):
        # as soon as the vehicle really arrives, we can undo this because its then reflected in the capacity
        yield task._arrived_at_charging_station
        availability = self._virtual_charging_infrastructure.get_available_capacity()
        availability[task.destination] += 1
        self._virtual_charging_infrastructure.update(availability=availability)

    def _track_task(self, task):
        yield AnyOf(self._env, [task.task_finished, self._world.simulation_finished])

        self._task_transactions.append(
            {
                "start_time": task._start_time,
                "scheduled_time": task._scheduled_time,
                "end_time": self._env.now,
                "vehicle": task._vehicle.id,
                "state": task.state,
                "fleet": task._vehicle.fleet.id,
                "charging_station": task._charging_station.location,
                "waiting_time": task.waiting_time,
                "charging_duration": task.charging_duration,
                "kWh_charged": task.kWh_charged,
            }
        )

    @property
    def task_transactions(self):
        return pd.DataFrame(self._task_transactions)
