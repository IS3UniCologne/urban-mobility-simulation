class TripCharacteristics:
    """

    INFO: Extend this class to add more granular trip chars (e.g., temperature, precipitation)
    """

    __slots__ = ("_distance",)

    def __init__(self, distance):  # noqa: ANN001, ANN204
        self._distance = distance

    @property
    def distance(self):  # noqa: ANN201
        return self._distance
