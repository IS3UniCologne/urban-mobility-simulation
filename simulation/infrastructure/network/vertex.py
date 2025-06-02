from simulation.environment.position import Position


class Vertex:
    __slots__ = ("_position",)

    def __init__(self, position: Position):  # noqa: ANN204
        self._position = position

    @property
    def position(self) -> Position:
        return self._position
