from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.interface.search_engine_interface import (
        SearchEngineInterface,
    )
    from simulation.operator.interface.vehicle_allocation_engine_interface import (
        VehicleAllocationEngineInterface,
    )
    from simulation.operator.operations_management.operations import OperationsInterface
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.tasks.transport_task import TransportTask

from simulation.helper.configuration.enums import OperatorMode, TransactionState
from simulation.helper.time import SimulationTime
from simulation.infrastructure.helper import timetable
from simulation.operator.operator import Operator


class PublicTransitOperator(Operator):
    __slots__ = (
        "_busses",
        "_time",
        "_timetable",
        "_total_missed_car_trips",
        "_tracked_demands",
    )

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        charging_infrastructure: ChargingInfrastructure,
        operations: OperationsInterface,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
    ) -> None:
        super().__init__(
            sim=sim,
            fleet=fleet,
            charging_infrastructure=charging_infrastructure,
            operations=operations,
            search_engine=search_engine,
            allocation_engine=allocation_engine,
        )
        self._mode = OperatorMode.PUBLIC_TRANSIT

        # TODO: Do we need this? Isn't this already covered by the transaction log?
        self._tracked_demands = set()

        self._timetable = timetable
        self._time = SimulationTime(self._env)
        self._busses = []

    def pay_for_fulfilled_transportation_task(
        self,
        user,  # noqa: ANN001
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ) -> None:
        # Check the price of the bus
        payment = selected_transportation_alternative.price

        # Add Transaction to Log
        # Check that all variables do really exist for the bus
        self.log_transaction(
            transportation_task, selected_transportation_alternative, "Fulfilled"
        )

        self.logger.info("New Payment (%s) received from User %s.", payment, user.uid)

    def withdraw_transportation_task(
        self,
        user,  # noqa: ANN001
        transportation_task: TransportTask,
        state: TransactionState = TransactionState.WITHDRAWN,
    ) -> None:
        self.log_transaction(transportation_task, None, state=state)

        self.logger.debug("Missed trip of User %s.", user.uid)
