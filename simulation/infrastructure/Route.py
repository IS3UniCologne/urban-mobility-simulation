from simulation.environment.position import Position


class Route:
    def __init__(self, origin: Position, destination: Position):
        self._origin = origin
        self._destination = destination

    @property
    def origin(self):
        return self._origin

    @property
    def destination(self):
        return self._destination