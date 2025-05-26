from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)


class TransportationAlternativeBrowser:
    __slots__ = ("_transportation_alternatives",)

    def __init__(self):  # noqa: ANN204
        self._transportation_alternatives = []

    def add_transportation_alternative(  # noqa: ANN201
        self,
        transportation_alternative: TransportationAlternative
        | TransportationAlternativeRideHailing,  # TODO: this should be a common interface
    ):
        self._transportation_alternatives.append(transportation_alternative)

    @property
    def transportation_alternatives(self):  # noqa: ANN201
        return self._transportation_alternatives

    @transportation_alternatives.setter
    def transportation_alternatives(self, transportation_alternatives):  # noqa: ANN001, ANN202
        self._transportation_alternatives = transportation_alternatives

    def __str__(self) -> str:
        return str(self._transportation_alternatives)
