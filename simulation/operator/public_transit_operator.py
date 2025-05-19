import logging

from simpy import Environment

from simulation.helper.time import SimulationTime
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.infrastructure.helper import timetable
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operator import Operator
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask


class PublicTransitOperator(Operator):
    __slots__ = (
        "_timetable",
        "_time",
        "_busses",
        "_total_missed_car_trips",
        "_tracked_demands",
    )

    def __init__(
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
        PaymentInterface.__init__(self)
        self._timetable = timetable
        self._env = env
        self._fleet = fleet
        self._time = SimulationTime(env)
        self._busses = []

    def pay_for_fulfilled_transportation_task(
        self,
        user,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ):
        # Check the price of the bus
        payment = selected_transportation_alternative.price

        self.increase_total_revenue(payment)

        # Add Transaction to Log
        # Check that all variables do really exist for the bus
        self.log_transaction(
            transportation_task, selected_transportation_alternative, "Fulfilled"
        )

        logging.info(
            f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def withdraw_transportation_task(
        self, user, transportation_task: TransportTask, state="Widthdrawn"
    ):
        self.increase_total_missed_trips(0)

        self.increase_total_missed_trips(1)

        self.log_transaction(transportation_task, None, state=state)

        logging.debug(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
