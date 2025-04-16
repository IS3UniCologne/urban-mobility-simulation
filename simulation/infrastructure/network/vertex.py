from simulation.environment.position import Position


class Vertex:
    __slots__ = ("_position",)

    def __init__(self, position: Position):
        self._position = position

    @property
    def position(self) -> Position:
        return self._position
