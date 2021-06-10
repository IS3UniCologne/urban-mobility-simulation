from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge
from typing import List

from simulation.infrastructure.network.vertex import Vertex


class Route:
    def __init__(self, origin: Position, destination: Position):
        self._origin = origin
        self._destination = destination
        self._route_segments: List[Edge] =  []

        distance = origin >> destination # euclidean distance
        self._route_segments.append(Edge(distance, Vertex(origin), Vertex(destination))) # Append Dummy Edge

    @property
    def origin(self):
        return self._origin

    @property
    def destination(self):
        return self._destination
    
    @property
    def route_segments(self):
        return self._route_segments

    @property
    def distance(self):
        distance = 0
        for rs in self.route_segments:
            distance += rs.distance
        return distance