import logging

from simpy import Environment

from simulation.agent.user import User
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operator import Operator
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask


class RideHailingOperator(Operator):
    __slots__ = ("_driver_payment_share",)

    def __init__(  # noqa: ANN204
        self,
        env: Environment,
        fleet: VehicleFleet,
        charging_infrastructure: ChargingInfrastructure,
        operations: OperationsInterface,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
    ):
        super().__init__(
            env,
            fleet,
            charging_infrastructure,
            operations,
            search_engine,
            allocation_engine,
        )

        self._driver_payment_share = (
            Configuration().ride_hailing_global.DRIVER_PAYMENT_SHARE
        )

    def pay_for_fulfilled_transportation_task(  # noqa: ANN201
        self,
        user,  # noqa: ANN001
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternativeRideHailing,
    ):
        payment = selected_transportation_alternative.price
        vehicle = selected_transportation_alternative.vehicle
        # we need to pay the driver costs
        if vehicle.__class__.__name__ == "RideHailingCar":
            self.increase_total_revenue(payment * (1 - self._driver_payment_share))
            vehicle.update_earned_money(payment)

        else:
            self.increase_total_revenue(payment)

        # Add Transaction to Log
        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state="Fulfilled",
        )

        logging.info(
            f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",  # noqa: G004
            extra={"clazz": self.__class__.__name__, "oid": self._fleet.id},
        )

    def withdraw_transportation_task(  # noqa: ANN201
        self, user: User, transportation_task: TransportTask, state: str | None = None
    ):
        # distance = transportation_task.origin >> transportation_task.destination
        # TODO: define price of the trip

        self.increase_total_missed_trips(1)

        # Add Transaction to Log
        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=None,
            state=state,
        )

        logging.info(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",  # noqa: G004
            extra={"clazz": self.__class__.__name__, "oid": self._fleet.id},
        )
