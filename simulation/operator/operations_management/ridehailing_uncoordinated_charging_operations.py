import dataclasses
from collections import namedtuple

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.operations import OperationsDependencies
from simulation.operator.operations_management.ride_hailing_operations import (
    RideHailingOperations,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)


class RideHailingUncoordinatedChargingOperations(RideHailingOperations):  # noqa: D101
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

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)

        self._deps = deps

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure = None
        self._charging_operations = None

    def execute(self):  # noqa: ANN201, D102
        # defer some of the initialization to after the operator has registered everything
        self._virtual_charging_infrastructure = VirtualChargingInfrastructure(
            sim=self._sim,
            charging_infrastructure=self._operator.charging_infrastructure,
            use_virtual_cs=True,
        )

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["id", "fleet", "charging_infrastructure"]
        )

        # TODO can we just use uid instead ?
        id = self._operator.uid.split("_")[1]
        vo = VirtualOperator(
            id=id,
            fleet=self._operator.fleet,
            charging_infrastructure=self._virtual_charging_infrastructure,
        )

        patched_deps = dataclasses.replace(
            self._deps, operator=vo
        )  # shallow copy, as we want to retain references to sim and world

        self._charging_operations = RideHailingBaseChargingOperations(patched_deps)

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
