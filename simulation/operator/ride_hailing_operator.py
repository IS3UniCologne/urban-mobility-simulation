from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.data_transfer_object.vehicle_allocation import (
        VehicleAllocation,
    )


from simulation.helper.enums import OperatorMode, TransactionState
from simulation.operator.operator import Operator, OperatorDependencies


class RideHailingOperator(Operator):
    """Operator for ride-hailing services."""

    __slots__ = ("_charging_infrastructure",)

    def __init__(self, deps: OperatorDependencies) -> None:
        super().__init__(deps=deps)
        self._mode = OperatorMode.RIDE_HAILING

    @property
    def charging_infrastructure(self) -> ChargingInfrastructure:
        """Return the charging infrastructure for electric vehicles."""
        if self._charging_infrastructure is None:
            raise ValueError(
                "Charging infrastructure must be provided for ride-hailing."
            )
        return self._charging_infrastructure

    def pay_for_fulfilled_transportation_task(  # noqa: ANN201, D102
        self,
        user: User,
        transportation_task: TransportRequest,
        vehicle_allocation: VehicleAllocation,
    ):
        selected_transportation_alternative = (
            vehicle_allocation.transportation_alternative
        )
        payment = selected_transportation_alternative.price

        # Add Transaction to Log
        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state=TransactionState.FULFILLED,
            energy_consumed=vehicle_allocation.energy_consumed,
        )

        self.logger.debug("New Payment (%s) received from User %s.", payment, user.uid)
