from collections import namedtuple  # noqa: D100

import pandas as pd

from simulation.context.simulation_context import SimulationContext
from simulation.helper.configuration.configuration import OperationsConfig
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.interface.operations_interface import OperationsInterface
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.world.world import World


class RideHailingUncoordinatedChargingOperations(OperationsInterface):  # noqa: D101
    __slots__ = (
        "_allow_queue",
        "_available_modes",
        "_available_modes_supply",
        "_charging_operations",
        "_config",
        "_distance_matrix",
        "_operations_config",
        "_operations_duration",
        "_sim",
        "_state_of_charge_threshold",
        "_time_between_operations",
        "_virtual_charging_infrastructure",
        "_world",
    )

    def __init__(
        self,
        sim: SimulationContext,
        distance_matrix: pd.DataFrame,
        operations_config: OperationsConfig,
        world: World,
    ) -> None:
        super().__init__(sim)
        self._sim = sim
        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        self._operations_config = operations_config
        self._charging_operations = None
        self._config = sim.config
        self._distance_matrix = distance_matrix
        self._time_between_operations = operations_config.TIME_BETWEEN_OPERATIONS
        self._operations_duration = operations_config.OPERATIONS_DURATION
        # self._available_modes = available_modes
        # self._available_modes_supply = available_modes_supply
        self._state_of_charge_threshold = operations_config.RECHARGE_THRESHOLD
        self._allow_queue = operations_config.ALLOW_QUEUE
        self._world = world

    def execute(self):  # noqa: ANN201, D102
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            sim=self._sim,
            charging_infrastructure=self._operator_reference.charging_infrastructure,
            use_virtual_cs=True,
        )

        self._charging_operations = RideHailingBaseChargingOperations(
            sim=self._sim,
            distance_matrix=self._distance_matrix,
            operations_config=self._operations_config,
            world=self._world,
        )

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["id", "fleet", "charging_infrastructure"]
        )
        # TODO can we just use uid instead ?
        id = self._operator_reference.uid.split("_")[1]
        self._charging_operations.register_operator_reference(
            VirtualOperator(
                id=id,
                fleet=self._operator_reference.fleet,
                charging_infrastructure=self._virtual_charging_infrastructure,
            )
        )

        # update virtual infra with vehicles on their way
        self._env.process(self._listen_for_tasks())

        yield self._env.process(self._charging_operations.execute())

    def _listen_for_tasks(self):  # noqa: ANN202
        while True:
            task = yield self._charging_operations.task_executed
            # update virtual infra with vehicles on their way
            self._update_after_sending(task)
            self._env.process(self._update_after_arrival(task))

    def _update_after_sending(self, task):  # noqa: ANN001, ANN202
        # Update virtual capacity when sending out a vehicle

        availability = (
            self._virtual_charging_infrastructure.get_available_capacity().copy()
        )
        availability[task.destination] -= 1
        self._virtual_charging_infrastructure.update(availability=availability)

    def _update_after_arrival(self, task):  # noqa: ANN001, ANN202
        # as soon as the vehicle really arrives, we can undo this because its then reflected in the capacity
        yield task._arrived_at_charging_station  # noqa: SLF001
        availability = (
            self._virtual_charging_infrastructure.get_available_capacity().copy()
        )
        availability[task.destination] += 1
        self._virtual_charging_infrastructure.update(availability=availability)

    @property
    def task_transactions(self):  # noqa: ANN201, D102
        return self._charging_operations.task_transactions
