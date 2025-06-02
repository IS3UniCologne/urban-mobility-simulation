import logging

from simpy import Environment

from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)
from simulation.operator.data_transfer_object.trip_record import TripRecord
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.transactions import TransactionLog
from simulation.operator.transactions.transaction import Transaction
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask


class Operator:
    operator_id = 0

    __slots__ = (
        "_allocation_engine",
        "_charging_infrastructure",
        "_env",
        "_fleet",
        "_operations",
        "_search_engine",
        "_total_fulfilled_trips",
        "_total_missed_revenue",
        "_total_missed_trips",
        "_total_revenue",
        "_transaction_log",
        "id",
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
        self.id = Operator.operator_id
        Operator.operator_id += 1

        self._env = env
        self._fleet = fleet
        self._charging_infrastructure = charging_infrastructure
        self._operations = operations

        self._search_engine = search_engine
        self._allocation_engine = allocation_engine

        self._total_revenue = 0
        self._total_fulfilled_trips = 0
        self._total_missed_trips = 0
        self._total_missed_revenue = 0

        self._transaction_log: TransactionLog = TransactionLog()

        self._operations.register_operator_reference(self)

        self._search_engine.register_fleet(self._fleet)

        self._env.process(self._operations.execute())

    @property
    def total_revenue(self):  # noqa: ANN201
        return self._total_revenue

    @property
    def total_fulfilled_trips(self):  # noqa: ANN201
        return self._total_fulfilled_trips

    @property
    def total_missed_trips(self):  # noqa: ANN201
        return self._total_missed_trips

    @property
    def total_missed_revenue(self):  # noqa: ANN201
        return self._total_missed_revenue

    @property
    def fleet(self):  # noqa: ANN201
        return self._fleet

    @property
    def charging_infrastructure(self):  # noqa: ANN201
        return self._charging_infrastructure

    def increase_total_revenue(self, additional_revenue):  # noqa: ANN001, ANN201
        self._total_fulfilled_trips += 1
        self._total_revenue += additional_revenue

    def increase_total_missed_trips(self, missed_revenue):  # noqa: ANN001, ANN201
        self._total_missed_revenue += missed_revenue
        self._total_missed_trips += 1

    @property
    def transaction_log(self):  # noqa: ANN201
        """
        Return the transaction log of the operator

        :return: TransactionLog
        """
        return self._transaction_log

    @property
    def transaction_df(self):  # noqa: ANN201
        """
        Return all transactions (fulfilled and missed) as a DataFrame

        DataFrame has the following columns
        "origin": Origin of Request
        "destination": Destination of Request
        "time_start": Trip Request Start Time
        "time_end": Trip Request End Time
        "price": Trip Price (0.0 if missed)
        "distance": (Expected) distance,
        "duration": Duration in minutes, 0.0 if missed
        "selected_vehicle_mode": Selected Vehicle Mode
        "state": Missed or Fulfilled
        "viable_vehicle_modes": List of viable modes for this trip (set 1 and 0 columnwise per Vehicle)

        :return: DataFrame
        """
        return self._transaction_log.to_dataframe()

    def log_transaction(
        self,
        transportation_task: TransportTask,
        transportation_alternative: TransportationAlternative
        | TransportationAlternativeRideHailing
        | None,
        state: str | None,
        trip_record: None | TripRecord = None,
    ) -> None:
        """
        Log a transaction in the transaction log.

        Parameters
        ----------
        transportation_task : TransportTask
            The transportation task that was fulfilled or missed.
        transportation_alternative : TransportationAlternative | TransportationAlternativeRideHailing | None
            The transportation alternative that was selected for the task.
        state : str | None
            The state of the transaction (e.g., "Fulfilled", "Missed").
        trip_record : None | TripRecord
            The trip record associated with the transaction. (If available)
        """
        # TODO:Check if wait times are correct once user refactoring is done
        if state is None:
            state = "Unknown"
        if transportation_alternative is None:
            transaction: Transaction = Transaction(
                vehicle_id=None,
                origin=transportation_task.origin.get_region_id(),
                destination=transportation_task.destination.get_region_id(),
                time_start=transportation_task.time,
                time_end=self._env.now,
                price=0.0,
                distance=transportation_task.origin >> transportation_task.destination,
                duration=0.0,
                selected_vehicle_mode="None",
                state=state,
                wait_time=transportation_task.actual_wait_time,
                energy_consumption=0.0,
                viable_vehicle_modes=transportation_task.viable_vehicle_modes,
            )
        elif isinstance(
            transportation_alternative, TransportationAlternativeRideHailing
        ):
            transaction: Transaction = Transaction(
                vehicle_id=transportation_alternative.vehicle.id,
                origin=transportation_alternative.route.origin.get_region_id(),
                destination=transportation_alternative.route.destination.get_region_id(),
                time_start=transportation_task.time,
                time_end=self._env.now,
                price=transportation_alternative.price,
                distance=transportation_alternative.distance,
                duration=transportation_alternative.duration,
                selected_vehicle_mode=transportation_alternative.vehicle.__class__.__name__
                + "_"
                + str(transportation_alternative.vehicle.is_electric),
                state=state,
                wait_time=transportation_task.actual_wait_time,
                viable_vehicle_modes=transportation_task.viable_vehicle_modes,
                energy_consumption=transportation_alternative.energy_consumed,
                waiting_time=transportation_alternative.waiting_time,
                pick_up_time=transportation_alternative.pick_up_time,
                selected_vehicle_EV=transportation_alternative.vehicle.is_electric,
            )
        else:
            transaction: Transaction = Transaction(
                vehicle_id=transportation_alternative.vehicle.id,
                origin=transportation_alternative.route.origin.get_region_id(),
                destination=transportation_alternative.route.destination.get_region_id(),
                time_start=transportation_task.time,
                time_end=self._env.now,
                price=transportation_alternative.price,
                distance=transportation_alternative.distance,
                duration=transportation_alternative.duration,
                selected_vehicle_mode=transportation_alternative.vehicle.mode.name,
                state=state,
                wait_time=transportation_task.actual_wait_time,
                energy_consumption=trip_record.energy_consumed
                if trip_record is not None
                else 0.0,
                viable_vehicle_modes=transportation_task.viable_vehicle_modes,
            )
        self._transaction_log.add_transaction(transaction)

    def pay_for_fulfilled_transportation_task(  # noqa: ANN201
        self,
        user,  # noqa: ANN001
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ):
        payment = selected_transportation_alternative.price
        self.increase_total_revenue(payment)

        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state="Fulfilled",
            trip_record=user.trip_record,
        )

        logging.info(
            f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",  # noqa: G004
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def withdraw_transportation_task(self, user, transportation_task: TransportTask):  # noqa: ANN001, ANN201
        self.increase_total_missed_trips(0)

        # Add Transaction to Log
        self.log_transaction(transportation_task, None, state="Missed")

        logging.debug(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",  # noqa: G004
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
