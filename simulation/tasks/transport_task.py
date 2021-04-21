from simulation.agent.agent import Agent
from simulation.environment.position import Position


class TransportTask:

    def __init__(self, origin: Position, destination: Position):
        self._origin = origin
        self._destination = destination

    @property
    def origin(self):
        pass

    @origin.setter
    def trip_origin(self, position: Position):
        self._origin = position

    @property
    def destination(self):
        pass

    @destination.setter
    def destination(self, position: Position):
        self._destination = position