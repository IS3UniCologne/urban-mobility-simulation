class TripCharacteristics:
    """

    INFO: Extend this class to add more granular trip chars (e.g., temperature, precipitation)
    """

    __slots__ = ("_distance",)

    def __init__(self, distance):
        self._distance = distance

    @property
    def distance(self):
        return self._distance
