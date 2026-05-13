class TripCharacteristics:  # noqa: D100
    """

    INFO: Extend this class to add more granular trip chars (e.g., temperature, precipitation)
    """  # noqa: D200, D400

    __slots__ = ("_distance",)

    def __init__(self, distance):  # noqa: ANN001, ANN204
        self._distance = distance

    @property
    def distance(self):  # noqa: ANN201, D102
        return self._distance
