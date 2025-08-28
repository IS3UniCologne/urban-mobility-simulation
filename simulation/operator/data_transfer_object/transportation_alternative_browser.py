from simulation.operator.data_transfer_object.transportation_alternative import (  # noqa: D100
    TransportationAlternative,
)


class TransportationAlternativeBrowser:  # noqa: D101
    __slots__ = ("_transportation_alternatives",)

    def __init__(self) -> None:
        self._transportation_alternatives: list[TransportationAlternative] = []

    def add_transportation_alternative(  # noqa: D102
        self, transportation_alternative: TransportationAlternative
    ) -> None:
        self._transportation_alternatives.append(transportation_alternative)

    @property
    def transportation_alternatives(self) -> list[TransportationAlternative]:  # noqa: D102
        return self._transportation_alternatives

    @transportation_alternatives.setter
    def transportation_alternatives(
        self, transportation_alternatives: list[TransportationAlternative]
    ) -> None:
        self._transportation_alternatives = transportation_alternatives

    def __str__(self) -> str:  # noqa: D105
        if not self._transportation_alternatives:
            return "[]"

        # Use the __str__ method of each alternative instead of __repr__
        alternatives_str = [str(alt) for alt in self._transportation_alternatives]
        return "[" + ", ".join(alternatives_str) + "]"
