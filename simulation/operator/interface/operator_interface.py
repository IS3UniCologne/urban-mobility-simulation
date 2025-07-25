"""Generic operator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    import simpy

    from simulation.agent.user import User
    from simulation.helper.configuration.enums import OperatorMode
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.interface.search_engine_interface import (
        SearchEngineInterface,
    )
    from simulation.operator.interface.vehicle_allocation_engine_interface import (
        VehicleAllocationEngineInterface,
    )
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.tasks.transport_task import TransportTask


class OperatorInterface(ABC, SimulationBase):
    """
    Abstract interface for all transportation operators.

    This interface defines the common contract that all operators
    (ride-hailing, shared vehicle, public transport) must implement.
    """

    @property
    @abstractmethod
    def mode(self) -> OperatorMode:
        """Return the operator mode."""
        pass

    @abstractmethod
    def initialize(self, env: simpy.Environment) -> None:
        """Initialize the operator with simulation environment."""
        pass

    @property
    @abstractmethod
    def search_engine(self) -> SearchEngineInterface:
        """Return the search engine for this operator."""
        pass

    @property
    @abstractmethod
    def assignment_engine(self) -> VehicleAllocationEngineInterface:
        """Return the vehicle assignment engine for this operator."""
        pass

    @abstractmethod
    def start_operations(self) -> None:
        """Start operator-specific processes."""
        pass

    @property
    @abstractmethod
    def fleet(self) -> VehicleFleet:
        """Return the vehicle fleet for this operator."""
        pass

    @abstractmethod
    def withdraw_transportation_task(
        self, user: User, transportation_task: TransportTask, state: str | None = None
    ) -> None:
        """
        Withdraw a transportation task.

        Parameters
        ----------
        user : User
            The user who requested the task.
        transportation_task : TransportTask
            The task to withdraw.
        state : str | None, optional
            The state of the task after withdrawal.
        """
        pass

    @abstractmethod
    def pay_for_fulfilled_transportation_task(
        self,
        user: User,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ) -> None:
        """
        Process payment for a fulfilled transportation task.

        Parameters
        ----------
        user : User
            The user who requested the task.
        transportation_task : TransportTask
            The fulfilled task.
        selected_transportation_alternative : TransportationAlternative
            The selected transportation alternative for the task.
        """
        pass
