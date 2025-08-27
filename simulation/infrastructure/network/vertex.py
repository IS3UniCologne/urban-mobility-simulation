from simulation.environment.position import Position  # noqa: D100


class Vertex:  # noqa: D101
    __slots__ = ("_position",)

    def __init__(self, position: Position):  # noqa: ANN204
        self._position = position

    @property
    def position(self) -> Position:  # noqa: D102
        return self._position
