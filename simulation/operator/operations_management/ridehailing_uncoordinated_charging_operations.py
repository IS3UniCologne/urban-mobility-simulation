"""Module for uncoordinated ride-hailing charging operations."""

from __future__ import annotations

import dataclasses
from collections import namedtuple
from typing import TYPE_CHECKING, Any

from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.operations_management.ridehailing_greedy_charging_operations import (
    RideHailingGreedyChargingOperations,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    import pandas as pd
    from simpy.events import Event

    from simulation.operator.data_transfer_object.charging_session import (
        ChargingSession,
    )
    from simulation.operator.operations_management.operations import (
        OperationsDependencies,
    )
from simulation.operator.operations_management.ride_hailing_operations import (
    RideHailingOperations,
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
            "VirtualOperator", ["fleet", "charging_infrastructure"]
        )

        vo = VirtualOperator(
            fleet=self._operator.fleet,
            charging_infrastructure=self._virtual_charging_infrastructure,
        )

        patched_deps = dataclasses.replace(
            self._deps, operator=vo
        )  # shallow copy, as we want to retain references to sim and world

        self._charging_operations = RideHailingGreedyChargingOperations(patched_deps)

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
