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
    def __init__(self, deps: ChoiceModelDependencies) -> None:
        super().__init__(deps=deps)

    def calculate_choice_probabilities(
        self, user: User, available_alternatives: TransportationAlternativeBrowser
    ) -> dict[TransportationAlternative, float]:
        alternatives = available_alternatives.transportation_alternatives

        if not alternatives:
            return {}

        alternatives_sorted = sorted(alternatives, key=lambda alt: alt.est_pickup_time)

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
        return frozenset(VehicleType.CAR)

    @property
    def accepted_operator_modes(self) -> frozenset[OperatorMode]:
        """
        Get a frozenset of operator modes accepted by this choice model.

        Returns
        -------
        frozenset[OperatorMode]
            Frozenset of accepted operator modes.
        """
        return frozenset(OperatorMode.RIDE_HAILING)
