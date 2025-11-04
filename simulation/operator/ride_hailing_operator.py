from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.tasks.transport_task import TransportTask


from simulation.helper.configuration.enums import OperatorMode, TransactionState
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
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ):
        payment = selected_transportation_alternative.price
        # # we need to pay the driver costs
        # TODO : What do we do about this? Do we want to keep the driver payment share ?
        # if vehicle.__class__.__name__ == "RideHailingCar":
        #     self.increase     _total_revenue(payment * (1 - self._driver_payment_share))
        #     vehicle.update_earned_money(payment)

        # Add Transaction to Log
        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state=TransactionState.FULFILLED,
        )

        self.logger.info("New Payment (%s) received from User %s.", payment, user.uid)
