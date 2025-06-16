from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)


class TransportationAlternativeBrowser:
    __slots__ = ("_transportation_alternatives",)

    def __init__(self) -> None:
        self._transportation_alternatives = []

    def add_transportation_alternative(
        self,
        transportation_alternative: TransportationAlternative
        | TransportationAlternativeRideHailing,  # TODO: this should be a common interface
    ) -> None:
        self._transportation_alternatives.append(transportation_alternative)

    @property
    def transportation_alternatives(self) -> None:
        return self._transportation_alternatives

    @transportation_alternatives.setter
    def transportation_alternatives(self, transportation_alternatives: list) -> None:
        self._transportation_alternatives = transportation_alternatives

    def __str__(self) -> str:
        return str(self._transportation_alternatives)
