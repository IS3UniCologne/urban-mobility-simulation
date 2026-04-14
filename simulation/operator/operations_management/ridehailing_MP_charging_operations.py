from __future__ import annotations  # noqa: D100

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import pandas as pd
from simpy import AnyOf, Event

from simulation.helper.configuration.configuration import (
    RideHailingMPChargingOperationsConfig,
)
from simulation.helper.exceptions import TaskAborted
from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
    VirtualChargingInfrastructure,
)
from simulation.operator.data_transfer_object import ChargingSession
from simulation.operator.operations_management.ride_hailing_operations import (
    RideHailingOperations,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from simulation.operator.operations_management.operations import (
        OperationsDependencies,
    )


class RideHailingMPChargingOperations(RideHailingOperations):
    """Ridehailing Operations for Charging with Mathematical Programming / Optimization."""

    # TODO: Do we want to keep this in its current form as part of the core simulation?
    __slots__ = (
        "_algo",
        "_job_transactions",
        "_sim",
        "_state_of_charge_threshold",
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

        self._job_transactions: list[dict] = []

        self._virtual_charging_infrastructure: VirtualChargingInfrastructure | None = (
            None
        )

    def execute(self) -> Generator[Event, None, None]:  # noqa: D102
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

                session = ChargingSession.create(
                    sim=self._sim, vehicle=v, charging_station=c
                )

                # Track task completion
                self._env.process(self._track_session(session))

                self.logger.debug(
                    "Processing charging session for vehicle %s.", session.vehicle.uid
                )
                self._env.process(self._execute_autonomous_charging_session(session))

                # Update virtual capacity when sending out a vehicle
                availability = (
                    self._virtual_charging_infrastructure.get_available_capacity()
                )
                availability[session.destination] -= 1
                self._virtual_charging_infrastructure.update(availability=availability)
                # and look out for when it arrives
                self._env.process(self._update_after_arrival(session))

    def _update_after_arrival(
        self, session: ChargingSession
    ) -> Generator[Event, Any, None]:
        # as soon as the pre_queuing or pre_charging checkpoint event is triggered, we know the vehicle has arrived and
        # is either occupying a slot in the queue, at the plugs, or the task has aborted
        try:
            yield AnyOf(
                self._sim.env,
                [session.pre_queuing_checkpoint, session.pre_charging_checkpoint],
            )
        except TaskAborted:
            # Should never happen with full knowledge, keep around just in case
            self.logger.warning(
                "Charging session for vehicle %s aborted before start of charging. Releasing assumed capacity.",
                session.vehicle.uid,
            )
        finally:
            availability = (
                self._virtual_charging_infrastructure.get_available_capacity()
            )
            availability[session.destination] += 1
            self._virtual_charging_infrastructure.update(availability=availability)

    def _track_session(self, session: ChargingSession) -> Generator[AnyOf, Any, None]:
        yield AnyOf(self._env, [session.finished, self._world.simulation_finished])
        self._job_transactions.append(
            {
                "start_time": session.start_time,
                "estimated_arrival_time": session.estimated_arrival_time,
                "scheduled_time": session.scheduled_time,
                "end_time": self._env.now,
                "vehicle": session.vehicle.uid,
                "fleet": session.vehicle.fleet.uid,
                "charging_station": session.charging_station.location,
                "waiting_time": session.waiting_time,
                "charging_duration": session.charging_duration,
                "estimated_completion_time": session.estimated_completion_time,
                "kWh_charged": session.kWh_charged,
            }
        )

    @property
    def job_transactions(self) -> pd.DataFrame:  # noqa: D102
        return pd.DataFrame(self._job_transactions)
