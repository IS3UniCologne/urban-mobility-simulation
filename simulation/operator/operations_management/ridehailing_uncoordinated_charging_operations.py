from collections import namedtuple

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)


class RideHailingUncoordinatedChargingOperations(OperationsInterface):
    __slots__ = (
        "_allow_queue",
        "_available_modes",
        "_available_modes_supply",
        "_charging_operations",
        "_config",
        "_distance_matrix",
        "_operation_duration",
        "_state_of_charge_threshold",
        "_time_between_operations",
        "_virtual_charging_infrastructure",
    )

    def __init__(  # noqa: ANN204
        self,
        env,  # noqa: ANN001
        distance_matrix,  # noqa: ANN001
        time_between_operations,  # noqa: ANN001
        operation_duration,  # noqa: ANN001
        available_modes,  # noqa: ANN001
        available_modes_supply,  # noqa: ANN001
        state_of_charge_threshold,  # noqa: ANN001
        allow_queue,  # noqa: ANN001
    ):
        super(RideHailingUncoordinatedChargingOperations, self).__init__(env=env)  # noqa: UP008
        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        self._charging_operations = None

        self._config = Configuration()

        self._distance_matrix = distance_matrix
        self._time_between_operations = time_between_operations
        self._operation_duration = operation_duration
        self._available_modes = available_modes
        self._available_modes_supply = available_modes_supply
        self._state_of_charge_threshold = state_of_charge_threshold
        self._allow_queue = allow_queue

    def execute(self):  # noqa: ANN201
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            env=self._env,
            charging_infrastructure=self._operator_reference.charging_infrastructure,
            use_virtual_cs=True,
        )

        self._charging_operations = RideHailingBaseChargingOperations(
            env=self._env,
            distance_matrix=self._distance_matrix,
            time_between_operations=self._time_between_operations,
            operation_duration=self._operation_duration,
            available_modes=self._available_modes,
            available_modes_supply=self._available_modes_supply,
            state_of_charge_threshold=self._state_of_charge_threshold,
            allow_queue=self._allow_queue,
        )

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["id", "fleet", "charging_infrastructure"]
        )
        self._charging_operations.register_operator_reference(
            VirtualOperator(
                id=self._operator_reference.id,
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
    def task_transactions(self):  # noqa: ANN201
        return self._charging_operations.task_transactions
