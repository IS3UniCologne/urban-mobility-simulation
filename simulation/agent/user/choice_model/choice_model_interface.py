"""Interface for vehicle choice models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.agent.user.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import ChoiceModelConfig
    from simulation.helper.configuration.enums import OperatorMode, VehicleType
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )


@dataclass(frozen=True, slots=True)
class ChoiceModelDependencies:
    """
    Dependencies for the Choice Model.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    choice_model_config : ChoiceModelConfig
        Configuration for the choice model.
    """

    sim: SimulationContext
    choice_model_config: ChoiceModelConfig


class ChoiceModelInterface(SimulationBase, ABC):
    """
    Interface for calculating choice probabilities over transportation alternatives.

    Parameters
    ----------
    deps : ChoiceModelDependencies
        Dependencies required to initialize the choice model.
    """

    def __init__(self, deps: ChoiceModelDependencies) -> None:
        super().__init__(deps.sim)

    @staticmethod
    def from_deps(deps: ChoiceModelDependencies) -> ChoiceModelInterface:
        """
        Create choice model instance from dependencies.

        Parameters
        ----------
        deps : ChoiceModelDependencies
            Dependencies required to create the choice model.

        Returns
        -------
        ChoiceModelInterface
            The initialized choice model instance.
        """
        choice_model_type = deps.choice_model_config.CHOICE_MODEL_TYPE
        return choice_model_type(deps)

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
        dict
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
        frozenset of VehicleType
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
        frozenset of OperatorMode
            Frozenset of accepted operator modes.
        """
        pass
