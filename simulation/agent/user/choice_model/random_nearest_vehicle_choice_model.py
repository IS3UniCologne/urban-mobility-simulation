"""Simple choice model that selects a mode at random and picks the nearest vehicle of that mode."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from simulation.agent.user.choice_model.choice_model_interface import (
    ChoiceModelInterface,
)
from simulation.helper.configuration.enums import OperatorMode, VehicleType

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )


class RandomModeNearestVehicleChoiceModel(ChoiceModelInterface):
    """
    Simple choice model that randomly selects a mode then picks the nearest vehicle.

    Steps:
    1. Group alternatives by operator mode
    2. Randomly select one mode with equal probability
    3. Within that mode, select the vehicle closest to the user
    """

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._rng = sim.random_manager.get_rng(
            component_name="RANDOM_MODE_NEAREST_VEHICLE_CHOICE_MODEL"
        )

    def calculate_choice_probabilities(
        self, user: User, available_alternatives: TransportationAlternativeBrowser
    ) -> dict[TransportationAlternative, float]:
        """
        Calculate choice probabilities: random mode, then nearest vehicle.

        Parameters
        ----------
        user : User
            The user making the choice.
        available_alternatives : TransportationAlternativeBrowser
            Available transportation alternatives.

        Returns
        -------
        dict[TransportationAlternative, float]
            Mapping of alternatives to probabilities. One alternative gets 1.0,
            all others get 0.0.
        """
        alternatives = available_alternatives.transportation_alternatives

        if not alternatives:
            return {}

        # Group alternatives by mode
        alternatives_by_mode: dict[OperatorMode, list[TransportationAlternative]] = (
            defaultdict(list)
        )
        for alt in alternatives:
            alternatives_by_mode[alt.operator.mode].append(alt)

        # Randomly select a mode (uniform probability)
        available_modes = list(alternatives_by_mode.keys())
        selected_mode = self._rng.choice(available_modes)

        # Get alternatives in selected mode
        selected_mode_alternatives = alternatives_by_mode[selected_mode]

        # Find the nearest vehicle within the selected mode
        nearest_alternative = self._select_nearest_vehicle(
            user, selected_mode_alternatives
        )

        # Assign probability 1.0 to selected alternative, 0.0 to all others
        probabilities = {alt: 0.0 for alt in alternatives}
        probabilities[nearest_alternative] = 1.0

        return probabilities

    def _select_nearest_vehicle(
        self, user: User, alternatives: list[TransportationAlternative]
    ) -> TransportationAlternative:
        """
        Select the nearest vehicle from a list of alternatives.

        Parameters
        ----------
        user : User
            The user making the choice.
        alternatives : list[TransportationAlternative]
            List of alternatives to choose from.

        Returns
        -------
        TransportationAlternative
            The alternative with the nearest vehicle.
        """
        if len(alternatives) == 1:
            return alternatives[0]

        # Calculate distance to each vehicle
        nearest_alt = None
        min_distance = float("inf")

        for alt in alternatives:
            distance = user.position >> alt.vehicle.position

            if distance < min_distance:
                min_distance = distance
                nearest_alt = alt

        return nearest_alt if nearest_alt else alternatives[0]

    @property
    def accepted_vehicle_types(self) -> frozenset[VehicleType]:
        """
        Get a frozenset of vehicle types accepted by this choice model.

        Returns
        -------
        frozenset[VehicleType]
            Frozenset of accepted vehicle types.
        """
        return frozenset(vt for vt in VehicleType)

    @property
    def accepted_operator_modes(self) -> frozenset[OperatorMode]:
        """
        Get a frozenset of operator modes accepted by this choice model.

        Returns
        -------
        frozenset[OperatorMode]
            Frozenset of accepted operator modes.
        """
        return frozenset(mode for mode in OperatorMode)
