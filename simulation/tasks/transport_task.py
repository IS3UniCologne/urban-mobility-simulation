from simulation.agent.agent import Agent
from simulation.environment.position import Position


class TransportTask:

    def __init__(self, time, origin: Position, destination: Position, viable_vehicle_modes):
        self._time = time
        self._origin = origin
        self._destination = destination
        self._viable_vehicle_modes = viable_vehicle_modes

    @property
    def time(self):
        return self._time

    @property
    def origin(self):
        return self._origin

    @origin.setter
    def origin(self, position: Position):
        self._origin = position

    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, position: Position):
        self._destination = position

    @property
    def viable_vehicle_modes(self):
        return self._viable_vehicle_modes

    def __str__(self):
        return f'From {self._origin} to {self._destination}'