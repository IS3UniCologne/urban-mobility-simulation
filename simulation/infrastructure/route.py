from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge
from typing import List

from simulation.infrastructure.network.vertex import Vertex


class Route:
    def __init__(self, origin: Position, destination: Position):
        self._origin = origin
        self._destination = destination
        self._route_segments: List[Edge] =  []

        self._route_segments.append(Edge(4500, Vertex(origin), Vertex(destination))) # Append Dummy Edge

    @property
    def origin(self):
        return self._origin

    @property
    def destination(self):
        return self._destination
    
    @property
    def route_segments(self):
        return self._route_segments