"""Operator base class. Implements common operator functionality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import OperatorConfig
    from simulation.helper.enums import VehicleType
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.vehicle_allocation import (
        VehicleAllocation,
    )
    from simulation.operator.interface.operations_interface import OperationsInterface
    from simulation.operator.interface.search_engine_interface import (
        SearchEngineInterface,
    )
    from simulation.operator.interface.vehicle_allocation_engine_interface import (
        AllocationEngineInterface,
    )
    from simulation.world.world import World

from simulation.helper.enums import (
    AutonomyType,
    OperatorMode,
    PropulsionType,
    TransactionState,
)
from simulation.operator.interface.operator_interface import OperatorInterface
from simulation.operator.operator_log import OperatorLog
from simulation.operator.operator_log.operator_log_entry import (
    FulfilledOperatorLogEntry,
    MissedOperatorLogEntry,
)
from simulation.operator.vehicle_fleet import VehicleFleet, VehicleFleetDependencies


@dataclass(frozen=True, slots=True)
class OperatorDependencies:
    """Dependencies required to instantiate an Operator."""

    sim: SimulationContext
    config: OperatorConfig
    world: World
    charging_infrastructure: ChargingInfrastructure | None = None


class Operator(OperatorInterface):
    """Base class for all operators."""

    __slots__ = (
        "_allocation_engine",
        "_charging_infrastructure",
        "_context",
        "_env",
        "_fleet",
        "_mode",
        "_operations",
        "_operator_log",
        "_search_engine",
        "_sim",
    )

    def __init__(self, deps: OperatorDependencies) -> None:
        super().__init__(sim=deps.sim)

        self._sim: SimulationContext = deps.sim
        self._env = deps.sim.env
        self._config: OperatorConfig = deps.config
        self._charging_infrastructure: ChargingInfrastructure | None = (
            self._config.CHARGING_INFRASTRUCTURE.instance
            if self._config.CHARGING_INFRASTRUCTURE
            else None
        )

        self._operator_log: OperatorLog = OperatorLog()

    @staticmethod
    def from_deps(deps: OperatorDependencies) -> Operator:
        """Create an Operator instance from dependencies.

        Automatically selects the appropriate operator implementation based on the configuration.
        """
        operator_type = deps.config.OPERATOR_TYPE
        operator = operator_type(deps=deps)

        operator.build_operator_subcomponents(deps)

        operator.start_operations()

        deps.world.mobility_search.register_operator(operator)

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
                sim=deps.sim, config=deps.config.ALLOCATION_ENGINE_CONFIG, operator=self
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
    def operator_log(self) -> OperatorLog:
        """
        Return the operator log of the operator.

        Returns
        -------
        OperatorLog
            The operator log of this operator
        """
        return self._operator_log

    def start_operations(self) -> None:
        """Start the operations process."""
        self._env.process(self._operations.execute())

    def log_failed_allocation_attempt(
        self,
        user: User,
        transportation_task: TransportRequest,
        transportation_alternative: TransportationAlternative,
    ) -> None:
        """
        Log a failed vehicle allocation attempt.

        This represents a missed revenue opportunity for the operator - the user wanted
        to use this operator (chose it from available alternatives) but no vehicle could
        be allocated.

        Parameters
        ----------
        user : User
            The user who attempted allocation.
        transportation_task : TransportRequest
            The transportation task that was requested.
        transportation_alternative : TransportationAlternative
            The transportation alternative that was selected but could not be allocated.
        """
        transaction = self._create_missed_transaction(
            transportation_task, TransactionState.MISSED, transportation_alternative
        )

        self._operator_log.add_transaction(transaction)

    def log_transaction(
        self,
        transportation_task: TransportRequest,
        transportation_alternative: TransportationAlternative | None,
        state: TransactionState,
        energy_consumed: float | None = None,
    ) -> None:
        """
        Log a transaction in the transaction log.

        Parameters
        ----------
        transportation_task : TransportRequest
            The transportation task that was fulfilled or missed.
        transportation_alternative : TransportationAlternative | None
            The transportation alternative that was selected for the task.
        state : TransactionState
            The state of the transaction (e.g., FULFILLED, MISSED).
        energy_consumed : float | None
            The energy consumed during the trip.
        """
        # TODO:Check if wait times are correct once user refactoring is done
        if state == TransactionState.MISSED or transportation_alternative is None:
            transaction = self._create_missed_transaction(
                transportation_task, state, transportation_alternative
            )
        else:
            transaction = self._create_fulfilled_transaction(
                transportation_task, transportation_alternative, state, energy_consumed
            )

        self._operator_log.add_transaction(transaction)

    def _create_missed_transaction(
        self,
        transportation_task: TransportRequest,
        state: TransactionState,
        transportation_alternative: TransportationAlternative,
    ) -> MissedOperatorLogEntry:
        """Create a transaction for a missed trip."""
        return MissedOperatorLogEntry(
            origin=transportation_task.origin.get_region_id(),
            destination=transportation_task.destination.get_region_id(),
            time_start=transportation_task.creation_time,
            time_end=self._env.now,
            distance=transportation_task.origin << transportation_task.destination,
            accepted_vehicle_types=transportation_task.accepted_vehicle_types,
            state=state,
            price=transportation_alternative.price,
        )

    def _create_fulfilled_transaction(
        self,
        transportation_task: TransportRequest,
        transportation_alternative: TransportationAlternative,
        state: TransactionState,
        energy_consumed: float | None = None,
    ) -> FulfilledOperatorLogEntry:
        """Create a transaction for a fulfilled trip."""
        revenue = self._calculate_revenue(transportation_alternative)

        return FulfilledOperatorLogEntry(
            origin=transportation_alternative.route.origin.get_region_id(),
            destination=transportation_alternative.route.destination.get_region_id(),
            time_start=transportation_task.creation_time,
            time_end=self._env.now,
            distance=transportation_alternative.distance,
            accepted_vehicle_types=transportation_task.accepted_vehicle_types,
            state=state,
            price=transportation_alternative.price,
            revenue=revenue,
            duration=transportation_alternative.duration,
            vehicle_uid=transportation_alternative.vehicle.uid,
            selected_vehicle_type=transportation_alternative.vehicle.vehicle_type,
            pick_up_time=transportation_alternative.est_pickup_time,
            energy_consumption=energy_consumed if energy_consumed is not None else 0.0,
            selected_vehicle_EV=(
                transportation_alternative.vehicle.propulsion_type
                == PropulsionType.BATTERY_ELECTRIC
            ),
        )

    def _calculate_revenue(
        self, transportation_alternative: TransportationAlternative
    ) -> float:
        """
        Calculate operator revenue from a transportation alternative.

        For human-driven vehicles, deducts driver payment share if configured.

        Parameters
        ----------
        transportation_alternative : TransportationAlternative
            The selected transportation alternative.

        Returns
        -------
        float
            The revenue for the operator after deductions.
        """
        base_price = transportation_alternative.price

        if (
            transportation_alternative.vehicle.autonomy_type
            == AutonomyType.HUMAN_DRIVEN
        ):
            driver_share = getattr(
                self._config.OPERATIONS_CONFIG, "DRIVER_PAYMENT_SHARE", 0.0
            )
            return base_price * (1 - driver_share)

        return base_price

    def pay_for_fulfilled_transportation_task(  # noqa: D102
        self,
        user: User,
        transportation_task: TransportRequest,
        vehicle_allocation: VehicleAllocation,
    ) -> None:
        selected_transportation_alternative = (
            vehicle_allocation.transportation_alternative
        )
        payment = selected_transportation_alternative.price

        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=selected_transportation_alternative,
            state=TransactionState.FULFILLED,
            energy_consumed=vehicle_allocation.energy_consumed,
        )

        self.logger.debug("New Payment (%s) received from User %s.", payment, user.uid)

    def withdraw_transportation_task(  # noqa: D102
        self, user: User, transportation_task: TransportRequest, state: TransactionState
    ) -> None:
        # Add Transaction to Log
        self.log_transaction(transportation_task, None, state=state)

        self.logger.debug("Missed trip of User %s.", user.uid)
