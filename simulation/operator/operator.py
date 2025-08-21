from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.enums import (
        OperatorMode,
        TransactionState,
        VehicleType,
    )
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.trip_record import TripRecord
    from simulation.operator.interface.search_engine_interface import (
        SearchEngineInterface,
    )
    from simulation.operator.interface.vehicle_allocation_engine_interface import (
        VehicleAllocationEngineInterface,
    )
    from simulation.operator.operations_management.operations import OperationsInterface
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.tasks.transport_task import TransportTask

from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)
from simulation.operator.interface.operator_interface import OperatorInterface
from simulation.operator.transactions import TransactionLog
from simulation.operator.transactions.transaction import Transaction


class Operator(OperatorInterface):
    __slots__ = (
        "_allocation_engine",
        "_charging_infrastructure",
        "_context",
        "_env",
        "_env",
        "_fleet",
        "_mode",
        "_operations",
        "_search_engine",
        "_sim",
        "_transaction_log",
    )

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        operations: OperationsInterface,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
    ) -> None:
        super().__init__(sim)

        self._sim = sim
        self._env = sim.env
        self._fleet = fleet
        self._operations = operations

        self._search_engine = search_engine
        self._allocation_engine = allocation_engine

        self._transaction_log: TransactionLog = TransactionLog()

        self._operations.register_operator_reference(self)

        self._search_engine.register_fleet(self._fleet)

        self._env.process(self._operations.execute())

    @property
    def total_revenue(self) -> float:
        return self._transaction_log.total_revenue

    @property
    def total_fulfilled_trips(self) -> int:
        return self._transaction_log.total_fulfilled_trips

    @property
    def total_missed_trips(self) -> int:
        return self._transaction_log.total_missed_trips

    @property
    def total_missed_revenue(self) -> float:
        return self._transaction_log.total_missed_revenue

    @property
    def fleet(self) -> VehicleFleet:
        return self._fleet

    @property
    def vehicle_types(self) -> list[VehicleType]:
        """
        Get the available vehicle modes for this operator.

        Returns
        -------
        list[VehicleMode]
            List of available vehicle modes
        """
        return self._fleet.vehicle_types

    @property
    def transaction_log(self) -> TransactionLog:
        """
        Return the transaction log of the operator

        Returns
        -------
        TransactionLog
            The transaction log of this operator
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
        "selected_vehicle_type": Selected Vehicle Mode
        "state": Missed or Fulfilled
        "viable_vehicle_types": List of viable modes for this trip (set 1 and 0 columnwise per Vehicle)

        Returns
        -------
        DataFrame
            DataFrame containing all transaction data
        """
        return self._transaction_log.to_dataframe()

    def log_transaction(
        self,
        transportation_task: TransportTask,
        transportation_alternative: TransportationAlternative
        | TransportationAlternativeRideHailing
        | None,
        state: TransactionState | None,
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
                vehicle_uid=None,
                origin=transportation_task.origin.get_region_id(),
                destination=transportation_task.destination.get_region_id(),
                time_start=transportation_task.time,
                time_end=self._env.now,
                price=0.0,
                distance=transportation_task.origin >> transportation_task.destination,
                duration=0.0,
                selected_vehicle_type=None,
                state=state,
                wait_time=transportation_task.actual_wait_time,
                energy_consumption=0.0,
                viable_vehicle_types=transportation_task.viable_vehicle_types,
            )
        elif isinstance(
            transportation_alternative, TransportationAlternativeRideHailing
        ):
            transaction: Transaction = Transaction(
                vehicle_uid=transportation_alternative.vehicle.uid,
                origin=transportation_alternative.route.origin.get_region_id(),
                destination=transportation_alternative.route.destination.get_region_id(),
                time_start=transportation_task.time,
                time_end=self._env.now,
                price=transportation_alternative.price,
                distance=transportation_alternative.distance,
                duration=transportation_alternative.duration,
                selected_vehicle_type=transportation_alternative.vehicle.type,  # TODO: Check if this is correct
                state=state,
                wait_time=transportation_task.actual_wait_time,
                viable_vehicle_types=transportation_task.viable_vehicle_types,
                energy_consumption=transportation_alternative.energy_consumed,
                waiting_time=transportation_alternative.waiting_time,
                pick_up_time=transportation_alternative.pick_up_time,
                selected_vehicle_EV=transportation_alternative.vehicle.is_electric,
            )
        else:
            transaction: Transaction = Transaction(
                vehicle_uid=transportation_alternative.vehicle.uid,
                origin=transportation_alternative.route.origin.get_region_id(),
                destination=transportation_alternative.route.destination.get_region_id(),
                time_start=transportation_task.time,
                time_end=self._env.now,
                price=transportation_alternative.price,
                distance=transportation_alternative.distance,
                duration=transportation_alternative.duration,
                selected_vehicle_type=transportation_alternative.vehicle.type,  # TODO: Check if this is correct
                state=state,
                wait_time=transportation_task.actual_wait_time,
                energy_consumption=trip_record.energy_consumed
                if trip_record is not None
                else 0.0,
                viable_vehicle_types=transportation_task.viable_vehicle_types,
            )
        self._transaction_log.add_transaction(transaction)

    def pay_for_fulfilled_transportation_task(
        self,
        user: User,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ) -> None:
        payment = selected_transportation_alternative.price

        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state="Fulfilled",
            trip_record=user.trip_record,
        )

        self.logger.info("New Payment (%s) received from User %s.", payment, user.uid)

    def withdraw_transportation_task(
        self, user: User, transportation_task: TransportTask
    ) -> None:
        # Add Transaction to Log
        self.log_transaction(transportation_task, None, state="Missed")

        self.logger.debug("Missed trip of User %s.", user.uid)

    @property
    def mode(self) -> OperatorMode:
        """
        Get the mode of the operator.

        Returns
        -------
        OperatorMode
            The operator mode
        """
        return self._mode

    @property
    def search_engine(self) -> SearchEngineInterface:
        """
        Get the search engine used by this operator.

        Returns
        -------
        SearchEngineInterface
            The search engine instance
        """
        return self._search_engine

    @property
    def assignment_engine(self) -> VehicleAllocationEngineInterface:
        """
        Get the vehicle allocation engine used by this operator.

        Returns
        -------
        VehicleAllocationEngineInterface
            The vehicle allocation engine instance
        """
        return self._allocation_engine
