from simulation.infrastructure.network.vertex import Vertex


class Edge:
    def __init__(self, distance, origin: Vertex, destination: Vertex):
        self._distance = distance
        self._origin = origin
        self._destination = destination

    @property
    def distance(self):
        return self._distance

    @property
    def origin(self) -> Vertex:
        return self._origin

    @property
    def destination(self) -> Vertex:
        return self._destination