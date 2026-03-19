"""A vehicle choice model that selects the alternative with the minimum estimated pickup time."""

from simulation.agent.user.choice_model.choice_model_interface import (
    ChoiceModelDependencies,
    ChoiceModelInterface,
)
from simulation.agent.user.user import User
from simulation.helper.configuration.enums import OperatorMode, VehicleType
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)


class MinPickupTimeVehicleChoiceModel(ChoiceModelInterface):
    """
    Vehicle choice model based on minimum estimated pickup time.

    This model always selects the transportation alternative that has the
    shortest estimated pickup time for the user.
    """

    def __init__(self, deps: ChoiceModelDependencies) -> None:
        """
        Initialize the choice model.

        Parameters
        ----------
        deps : ChoiceModelDependencies
            The dependencies required by the choice model.
        """
        super().__init__(deps=deps)

    def calculate_choice_probabilities(
        self, user: User, available_alternatives: TransportationAlternativeBrowser
    ) -> dict[TransportationAlternative, float]:
        """
        Calculate the choice probabilities based on the minimum pickup time.

        Parameters
        ----------
        user : User
            The user making the choice.
        available_alternatives : TransportationAlternativeBrowser
            The browser containing available transportation alternatives.

        Returns
        -------
        dict[TransportationAlternative, float]
            A dictionary of alternatives and their associated choice probabilities.
        """
        alternatives = available_alternatives.transportation_alternatives

        if not alternatives:
            return {}

        alternatives_sorted = sorted(
            alternatives,
            key=lambda alt: alt.est_pickup_time
            if alt.est_pickup_time is not None
            else float("inf"),
        )

        return {alternatives_sorted[0]: 1.0} | {a: 0 for a in alternatives_sorted[1:]}

    @property
    def accepted_vehicle_types(self) -> frozenset[VehicleType]:
        """
        Get a frozenset of vehicle types accepted by this choice model.

        Returns
        -------
        frozenset[VehicleType]
            Frozenset of accepted vehicle types.
        """
        return frozenset([VehicleType.CAR])

    @property
    def accepted_operator_modes(self) -> frozenset[OperatorMode]:
        """
        Get a frozenset of operator modes accepted by this choice model.

        Returns
        -------
        frozenset[OperatorMode]
            Frozenset of accepted operator modes.
        """
        return frozenset([OperatorMode.RIDE_HAILING])
