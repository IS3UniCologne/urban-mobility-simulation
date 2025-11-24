"""Interface for vehicle choice models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.agent.user.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.enums import OperatorMode, VehicleType
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )


class ChoiceModelInterface(SimulationBase, ABC):
    """Interface for calculating choice probabilities over transportation alternatives."""

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)

    @abstractmethod
    def calculate_choice_probabilities(
        self, user: User, available_alternatives: TransportationAlternativeBrowser
    ) -> dict[TransportationAlternative, float]:
        """
        Calculate choice probabilities for available transportation alternatives.

        Parameters
        ----------
        user : User
            The user making the choice (provides population type, position, etc.).
        available_alternatives : TransportationAlternativeBrowser
            Available transportation alternatives to choose from.

        Returns
        -------
        dict[TransportationAlternative, float]
            Mapping of alternatives to their choice probabilities.
            Probabilities should sum to 1.0.
        """
        pass

    @property
    @abstractmethod
    def accepted_vehicle_types(self) -> frozenset[VehicleType]:
        """
        Get a frozenset of vehicle types accepted by this choice model.

        Returns
        -------
        frozenset[VehicleType]
            Frozenset of accepted vehicle types.
        """
        pass

    @property
    @abstractmethod
    def accepted_operator_modes(self) -> frozenset[OperatorMode]:
        """
        Get a frozenset of operator modes accepted by this choice model.

        Returns
        -------
        frozenset[OperatorMode]
            Frozenset of accepted operator modes.
        """
        pass
