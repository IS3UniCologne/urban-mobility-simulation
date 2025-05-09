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
        self._transactions.append(
            {
                "origin": selected_transportation_alternative.route.origin.get_region_id(),
                "destination": selected_transportation_alternative.route.destination.get_region_id(),
                "time_start": transportation_task.time,
                "time_end": self._env.now,
                "price": selected_transportation_alternative.price,
                "distance": selected_transportation_alternative.distance,
                "duration": selected_transportation_alternative.duration,
                "selected_vehicle_mode": selected_transportation_alternative.vehicle.mode.name,
                "state": "Fulfilled",
                **transportation_task.viable_vehicle_modes,
            }
        )
        logging.info(
            f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def withdraw_transportation_task(
        self, user, transportation_task: TransportTask, state=None
    ):
        self.increase_total_missed_trips(0)

        self.increase_total_missed_trips(1)

        self._transactions.append(
            {
                # Check if all variables are really needed for the bus
                "origin": transportation_task.origin.get_region_id(),
                "destination": transportation_task.destination.get_region_id(),
                "time_start": self._env.now,
                "time_end": self._env.now,
                "price": 0.0,
                "distance": transportation_task.origin
                >> transportation_task.destination,
                "duration": 0.0,
                "waiting_time": user._waiting_time,
                "pick_up_time": 0.0,
                "selected_vehicle_mode": "None",
                "selected_vehicle_EV": "None",
                "state": state,
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.debug(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
