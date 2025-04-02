from simulation.environment.position import Position


class TransportTask:

    __slots__ = ("_time", "_origin", "_destination", "_viable_vehicle_modes", "_max_wait_time", "_actual_wait_time") 

    def __init__(
        self,
        time,
        origin: Position,
        destination: Position,
        viable_vehicle_modes,
        max_wait_time=None,
        actual_wait_time=None,
    ):
        self._time = time
        self._origin = origin
        self._destination = destination
        self._viable_vehicle_modes = viable_vehicle_modes
        self._max_wait_time = max_wait_time
        self._actual_wait_time = actual_wait_time

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

    @property
    def max_wait_time(self):
        return self._max_wait_time

    @property
    def actual_wait_time(self):
        return self._actual_wait_time

    @actual_wait_time.setter
    def actual_wait_time(self, value):
        self._actual_wait_time = value

    def __str__(self):
        return f"From {self._origin} to {self._destination}"
