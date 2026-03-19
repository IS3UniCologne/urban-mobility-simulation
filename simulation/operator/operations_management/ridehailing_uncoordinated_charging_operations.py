"""Uncoordinated ridehailing charging."""

from __future__ import annotations

from collections import namedtuple
from typing import TYPE_CHECKING, Any

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.interface.operations_interface import OperationsInterface
from simulation.operator.operations_management.operations import OperationsDependencies
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    import pandas as pd
    from simpy.events import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import OperationsConfig
    from simulation.operator.data_transfer_object.charging_session import (
        ChargingSession,
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
        self._virtual_charging_infrastructure: VirtualChargingInfrastructure | None = (
            None
        )
        self._operations_config = operations_config
        self._charging_operations = None
        self._config = sim.config
        self._distance_matrix = distance_matrix
        self._time_between_operations = operations_config.TIME_BETWEEN_OPERATIONS
        self._operations_duration = operations_config.OPERATIONS_DURATION
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

        # hack a virtual operator reference into it?
        VirtualOperator = namedtuple(
            "VirtualOperator", ["id", "fleet", "charging_infrastructure"]
        )
        # TODO can we just use uid instead ?
        id = self._operator_reference.uid.split("_")[1]
        virtual_operator = VirtualOperator(
            id=id,
            fleet=self._operator_reference.fleet,
            charging_infrastructure=self._virtual_charging_infrastructure,
        )

        self._charging_operations = RideHailingBaseChargingOperations(
            deps=OperationsDependencies(
                sim=self._sim,
                operator=virtual_operator,
                world=self._world,
                operations_config=self._operations_config,
                distance_matrix=self._distance_matrix,
            )
        )
        # update virtual infra with vehicles on their way
        self._env.process(self._listen_for_sessions())

        yield self._env.process(self._charging_operations.execute())

    def _listen_for_sessions(self):  # noqa: ANN202
        while True:
            session: ChargingSession = yield self._charging_operations.job_executed
            # update virtual infra with vehicles on their way

            self._update_after_sending(session)
            self._env.process(self._update_after_arrival(session))

    def _update_after_sending(self, session: ChargingSession) -> None:
        # Update virtual capacity when sending out a vehicle

        availability = (
            self._virtual_charging_infrastructure.get_available_capacity().copy()
        )
        availability[session.destination] -= 1
        self._virtual_charging_infrastructure.update(availability=availability)

    def _update_after_arrival(
        self, session: ChargingSession
    ) -> Generator[Event, Any, None]:
        # as soon as the vehicle really arrives, we can undo this because its then reflected in the capacity
        yield session.arrived_at_charging_station
        availability = (
            self._virtual_charging_infrastructure.get_available_capacity().copy()
        )
        availability[session.destination] += 1
        self._virtual_charging_infrastructure.update(availability=availability)

    @property
    def job_transactions(self) -> pd.DataFrame:  # noqa: D102
        return self._charging_operations.job_transactions
