from simulation.infrastructure.network.vertex import Vertex


class Edge:
    __slots__ = ("_destination", "_distance", "_origin")

    def __init__(self, distance, origin: Vertex, destination: Vertex):  # noqa: ANN001, ANN204
        self._distance = distance
        self._origin = origin
        self._destination = destination

    @property
    def distance(self):  # noqa: ANN201
        return self._distance

    @property
    def origin(self) -> Vertex:
        return self._origin

    @property
    def destination(self) -> Vertex:
        return self._destination
