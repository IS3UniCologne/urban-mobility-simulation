"""Generic operator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.helper.enums import OperatorMode, TransactionState
    from simulation.operator.accounting import Ledger
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
    from simulation.operator.vehicle_fleet import VehicleFleet


class OperatorInterface(SimulationBase, ABC):
    """
    Abstract interface for all transportation operators.

    This interface defines the common contract that all operators
    (ride-hailing, shared vehicle, public transport) must implement.
    """

    @property
    @abstractmethod
    def mode(self) -> OperatorMode:
        """Return the operator mode."""

    @property
    @abstractmethod
    def search_engine(self) -> SearchEngineInterface:
        """Return the search engine for this operator."""

    @property
    @abstractmethod
    def allocation_engine(self) -> AllocationEngineInterface:
        """Return the vehicle allocation engine for this operator."""

    @property
    @abstractmethod
    def fleet(self) -> VehicleFleet:
        """Return the vehicle fleet for this operator."""

    @property
    @abstractmethod
    def operations(self) -> OperationsInterface:
        """Return the operations interface for this operator."""

    @property
    @abstractmethod
    def ledger(self) -> Ledger:
        """Return the ledger for this operator."""

    @abstractmethod
    def withdraw_transportation_task(
        self, user: User, transportation_task: TransportRequest, state: TransactionState
    ) -> None:
        """
        Withdraw a transportation task.

        Parameters
        ----------
        user : User
            The user who requested the task.
        transportation_task : TransportRequest
            The task to withdraw.
        state : TransactionState
            The state of the task after withdrawal.
        """

    @abstractmethod
    def pay_for_fulfilled_transportation_task(
        self,
        user: User,
        transportation_task: TransportRequest,
        vehicle_allocation: VehicleAllocation,
    ) -> None:
        """
        Process payment for a fulfilled transportation task.

        Parameters
        ----------
        user : User
            The user who requested the task.
        transportation_task : TransportRequest
            The fulfilled task.
        vehicle_allocation : VehicleAllocation
            The vehicle allocation for the task.
        """

    @abstractmethod
    def log_failed_allocation_attempt(
        self,
        user: User,
        transportation_task: TransportRequest,
        transportation_alternative: TransportationAlternative,
    ) -> None:
        """
        Log a failed vehicle allocation attempt.

        Parameters
        ----------
        user : User
            The user who requested the task.
        transportation_task : TransportRequest
                The task for which allocation failed.
        transportation_alternative : TransportationAlternative
            The transportation alternative that was selected but could not be allocated.
        """
