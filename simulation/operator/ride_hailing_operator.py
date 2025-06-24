from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
        TransportationAlternativeRideHailing,
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

from simulation.helper.configuration.enums import OperatorMode
from simulation.operator.operator import Operator


class RideHailingOperator(Operator):
    __slots__ = ("_driver_payment_share",)

    def __init__(  # noqa: ANN204
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        charging_infrastructure: ChargingInfrastructure,
        operations: OperationsInterface,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
    ):
        super().__init__(
            sim=sim,
            fleet=fleet,
            charging_infrastructure=charging_infrastructure,
            operations=operations,
            search_engine=search_engine,
            allocation_engine=allocation_engine,
        )
        self._mode = OperatorMode.RIDE_HAILING
        self._driver_payment_share = (
            self._sim.config.ride_hailing_global.DRIVER_PAYMENT_SHARE
        )

    def pay_for_fulfilled_transportation_task(  # noqa: ANN201
        self,
        user,  # noqa: ANN001
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternativeRideHailing,
    ):
        payment = selected_transportation_alternative.price
        # # we need to pay the driver costs
        # TODO : What do we do about this? Do we want to keep the driver payment share ?
        # if vehicle.__class__.__name__ == "RideHailingCar":
        #     self.increase_total_revenue(payment * (1 - self._driver_payment_share))
        #     vehicle.update_earned_money(payment)

        # Add Transaction to Log
        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state="Fulfilled",
        )

        self.logger.info("New Payment (%s) received from User %s.", payment, user.uid)

    def withdraw_transportation_task(
        self, user: User, transportation_task: TransportTask, state: str | None = None
    ) -> None:
        # distance = transportation_task.origin >> transportation_task.destination
        # TODO: define price of the trip

        # Add Transaction to Log
        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=None,
            state=state,
        )

        self.logger.info("Missed trip of User %s.", user.uid)
