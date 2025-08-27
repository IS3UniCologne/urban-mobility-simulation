"""Operator base class. Implements common operator functionality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase
from simulation.operator.operations_management.operations import (
    Operations,
    OperationsDependencies,
)
from simulation.operator.search_engine import SearchEngine, SearchEngineDependencies
from simulation.operator.vehicle_allocation_engine import (
    AllocationEngine,
    AllocationEngineDependencies,
)

if TYPE_CHECKING:
    from pandas import DataFrame

    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import OperatorConfig
    from simulation.helper.configuration.enums import VehicleType
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.trip_record import TripRecord
    from simulation.operator.interface.operations_interface import OperationsInterface
    from simulation.operator.interface.search_engine_interface import (
        SearchEngineInterface,
    )
    from simulation.operator.interface.vehicle_allocation_engine_interface import (
        AllocationEngineInterface,
    )
    from simulation.tasks.transport_task import TransportTask
    from simulation.world.world import World

from simulation.helper.configuration.enums import OperatorMode, TransactionState
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)
from simulation.operator.interface.operator_interface import OperatorInterface
from simulation.operator.transactions import TransactionLog
from simulation.operator.transactions.transaction import Transaction
from simulation.operator.vehicle_fleet import VehicleFleet, VehicleFleetDependencies


@dataclass(frozen=True, slots=True)
class OperatorDependencies:
    """Dependencies required to instantiate an Operator."""

    sim: SimulationContext
    config: OperatorConfig
    world: World
    charging_infrastructure: ChargingInfrastructure | None = None


class Operator(SimulationBase, OperatorInterface):
    """Base class for all operators."""

    __slots__ = (
        "_allocation_engine",
        "_charging_infrastructure",
        "_context",
        "_env",
        "_fleet",
        "_mode",
        "_operations",
        "_search_engine",
        "_sim",
        "_transaction_log",
    )

    def __init__(self, deps: OperatorDependencies) -> None:
        super().__init__(sim=deps.sim)

        self._sim = deps.sim
        self._env = deps.sim.env
        self._config = deps.config

        self._transaction_log: TransactionLog = TransactionLog()

    @classmethod
    def from_deps(cls, deps: OperatorDependencies) -> Operator:
        """Create an Operator instance from dependencies.

        Automatically selects the appropriate operator implementation based on the configuration.
        """
        operator_type = deps.config.OPERATOR_TYPE
        operator = operator_type(deps=deps)

        operator.build_operator_subcomponents(deps)

        operator.start_operations()

        return operator

    def build_operator_subcomponents(self, deps: OperatorDependencies) -> None:
        """Assemble components for the operator.

        Subclasses can override this for different construction behavior.
        """
        self._fleet = VehicleFleet.from_deps(
            VehicleFleetDependencies(
                sim=deps.sim,
                operator=self,
                world=deps.world,
                config=deps.config.FLEET_CONFIG,
            )
        )
        self._operations = Operations.from_deps(
            OperationsDependencies(
                sim=deps.sim,
                operator=self,
                world=deps.world,
                operations_config=deps.config.OPERATIONS_CONFIG,
                distance_matrix=deps.world.distance_matrix,
            )
        )
        self._search_engine = SearchEngine.from_deps(
            SearchEngineDependencies(
                sim=deps.sim, config=deps.config.SEARCH_ENGINE_CONFIG, operator=self
            )
        )
        self._allocation_engine = AllocationEngine.from_deps(
            AllocationEngineDependencies(
                sim=deps.sim, config=deps.config.ALLOCATION_ENGINE_CONFIG
            )
        )

    @property
    def allocation_engine(self) -> AllocationEngineInterface:
        """Get the allocation engine used by the operator."""
        return self._allocation_engine

    @property
    def search_engine(self) -> SearchEngineInterface:
        """Get the search engine used by the operator."""
        return self._search_engine

    @property
    def operations(self) -> OperationsInterface:
        """Get the operations used by the operator."""
        return self._operations

    @property
    def total_revenue(self) -> float:
        """Get the total revenue of the operator."""
        return self._transaction_log.metrics.total_revenue

    @property
    def total_fulfilled_trips(self) -> int:
        """Get the total number of fulfilled trips by the operator."""
        return self._transaction_log.metrics.total_fulfilled_trips

    @property
    def total_missed_trips(self) -> int:
        """Get the total number of missed trips by the operator."""
        return self._transaction_log.metrics.total_missed_trips

    @property
    def total_missed_revenue(self) -> float:
        """Get the total missed revenue by the operator."""
        return self._transaction_log.metrics.total_missed_revenue

    @property
    def fleet(self) -> VehicleFleet:
        """Get the vehicle fleet of the operator."""
        return self._fleet

    @fleet.setter
    def fleet(self, fleet: VehicleFleet) -> None:
        """Set the vehicle fleet of the operator."""
        self._fleet = fleet

    @property
    def vehicle_types(self) -> list[VehicleType]:
        """
        Get the available vehicle types for this operator.

        Returns
        -------
        list[VehicleType]
            List of available vehicle types
        """
        return self._fleet.vehicle_types

    @property
    def transaction_log(self) -> TransactionLog:
        """
        Return the transaction log of the operator.

        Returns
        -------
        TransactionLog
            The transaction log of this operator
        """
        return self._transaction_log

    # TODO: Remove in future versions in favor of transaction_log
    @property
    def transaction_df(self) -> DataFrame:
        """
        Return all transactions (fulfilled and missed) as a DataFrame.

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

    def start_operations(self) -> None:
        """Start the operations process."""
        self._env.process(self._operations.execute())

    def log_transaction(
        self,
        transportation_task: TransportTask,
        transportation_alternative: TransportationAlternative
        | TransportationAlternativeRideHailing
        | None,
        state: TransactionState,
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
                selected_vehicle_type=transportation_alternative.vehicle.vehicle_type,  # TODO: Check if this is correct
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
                selected_vehicle_type=transportation_alternative.vehicle.vehicle_type,  # TODO: Check if this is correct
                state=state,
                wait_time=transportation_task.actual_wait_time,
                energy_consumption=trip_record.energy_consumed
                if trip_record is not None
                else 0.0,
                viable_vehicle_types=transportation_task.viable_vehicle_types,
            )
        self._transaction_log.add_transaction(transaction)

    def pay_for_fulfilled_transportation_task(  # noqa: D102
        self,
        user: User,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ) -> None:
        payment = selected_transportation_alternative.price

        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state=TransactionState.FULFILLED,
            trip_record=user.trip_record,
        )

        self.logger.info("New Payment (%s) received from User %s.", payment, user.uid)

    def withdraw_transportation_task(  # noqa: D102
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
