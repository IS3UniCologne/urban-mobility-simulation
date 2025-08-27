from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
        TransportationAlternativeRideHailing,
    )
    from simulation.operator.operations_management.ride_hailing_operations import (
        RideHailingOperations,
    )
    from simulation.operator.ride_hailing_allocation_engine import (
        RideHailingAllocationEngine,
    )
    from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
    from simulation.tasks.transport_task import TransportTask


from simulation.helper.configuration.enums import OperatorMode, TransactionState
from simulation.operator.operator import Operator, OperatorDependencies


class RideHailingOperator(Operator):
    """Operator for ride-hailing services."""

    __slots__ = ("_charging_infrastructure",)

    def __init__(self, deps: OperatorDependencies) -> None:
        super().__init__(deps=deps)
        self._mode = OperatorMode.RIDE_HAILING
        if deps.charging_infrastructure is None:
            raise ValueError(
                "Charging infrastructure must be provided for RideHailingOperator"
            )
        self._charging_infrastructure = deps.charging_infrastructure

    @property
    def charging_infrastructure(self) -> ChargingInfrastructure:
        """Return the charging infrastructure for electric vehicles."""
        return self._charging_infrastructure

    @property
    def allocation_engine(self) -> RideHailingAllocationEngine:
        """Get the allocation engine used by the operator."""
        return cast("RideHailingAllocationEngine", self._allocation_engine)

    @property
    def search_engine(self) -> RideHailingSearchEngine:
        """Get the search engine used by the operator."""
        return cast("RideHailingSearchEngine", self._search_engine)

    @property
    def operations(self) -> RideHailingOperations:
        """Return the operations used by the ride-hailing operator."""
        return cast("RideHailingOperations", self._operations)

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
        #     self.increase     _total_revenue(payment * (1 - self._driver_payment_share))
        #     vehicle.update_earned_money(payment)

        # Add Transaction to Log
        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state=TransactionState.FULFILLED,
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
