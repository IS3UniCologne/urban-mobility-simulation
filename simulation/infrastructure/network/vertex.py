from simulation.environment.geodesic_position import GeodesicPosition  # noqa: D100


class Vertex:  # noqa: D101
    __slots__ = ("_position",)

    def __init__(self, position: GeodesicPosition) -> None:
        self._position = position

    @property
    def position(self) -> GeodesicPosition:
        """Get the position of the vertex."""
        return self._position
