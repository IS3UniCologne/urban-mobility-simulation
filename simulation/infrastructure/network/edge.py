from simulation.infrastructure.network.vertex import Vertex  # noqa: D100


class Edge:  # noqa: D101
    __slots__ = ("_destination", "_distance", "_origin")

    def __init__(self, distance: float, origin: Vertex, destination: Vertex) -> None:
        self._distance = distance
        self._origin = origin
        self._destination = destination

    @property
    def distance(self) -> float:  # noqa: D102
        return self._distance

    @property
    def origin(self) -> Vertex:  # noqa: D102
        return self._origin

    @property
    def destination(self) -> Vertex:  # noqa: D102
        return self._destination
