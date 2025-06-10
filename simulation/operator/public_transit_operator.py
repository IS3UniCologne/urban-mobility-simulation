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
        "_busses",
        "_time",
        "_timetable",
        "_total_missed_car_trips",
        "_tracked_demands",
    )

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
        PaymentInterface.__init__(self)
        self._timetable = timetable
        self._env = env
        self._fleet = fleet
        self._time = SimulationTime(env)
        self._busses = []

    def pay_for_fulfilled_transportation_task(  # noqa: ANN201
        self,
        user,  # noqa: ANN001
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
            "New Payment (%s) received from User %s. Current Total Revenue: %s.",
            payment,
            user.id,
            self.total_revenue,
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def withdraw_transportation_task(  # noqa: ANN201
        self,
        user,  # noqa: ANN001
        transportation_task: TransportTask,
        state="Widthdrawn",  # noqa: ANN001
    ):
        self.increase_total_missed_trips(0)

        self.increase_total_missed_trips(1)

        self.log_transaction(transportation_task, None, state=state)

        logging.debug(
            "Missed trip of User %s. Current Total Revenue: %s - Total Trips: %s - Missed Trips %s.",
            user.id,
            self.total_revenue,
            self.total_fulfilled_trips,
            self.total_missed_trips,
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
