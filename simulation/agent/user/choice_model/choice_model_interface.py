"""Interface for vehicle choice models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )


class ChoiceModelInterface(ABC):
    """Interface for calculating choice probabilities over transportation alternatives."""

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
