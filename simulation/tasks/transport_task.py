from simulation.environment.position import Position
from simulation.helper.types import SimTime


class TransportTask:
    __slots__ = (
        "_actual_wait_time",
        "_destination",
        "_max_wait_time",
        "_origin",
        "_time",
        "_viable_vehicle_types",
    )

    def __init__(  # noqa: ANN204
        self,
        time: SimTime,
        origin: Position,
        destination: Position,
        viable_vehicle_types,  # noqa: ANN001
        max_wait_time=None,  # noqa: ANN001
        actual_wait_time=None,  # noqa: ANN001
    ):
        self._time = time
        self._origin = origin
        self._destination = destination
        self._viable_vehicle_types = viable_vehicle_types
        self._max_wait_time = max_wait_time
        self._actual_wait_time = actual_wait_time

    @property
    def time(self):  # noqa: ANN201
        return self._time

    @property
    def origin(self):  # noqa: ANN201
        return self._origin

    @origin.setter
    def origin(self, position: Position):  # noqa: ANN202
        self._origin = position

    @property
    def destination(self):  # noqa: ANN201
        return self._destination

    @destination.setter
    def destination(self, position: Position):  # noqa: ANN202
        self._destination = position

    @property
    def viable_vehicle_types(self):  # noqa: ANN201
        return self._viable_vehicle_types

    @property
    def max_wait_time(self):  # noqa: ANN201
        return self._max_wait_time

    @property
    def actual_wait_time(self):  # noqa: ANN201
        return self._actual_wait_time

    @actual_wait_time.setter
    def actual_wait_time(self, value):  # noqa: ANN001, ANN202
        self._actual_wait_time = value

    def __str__(self):  # noqa: ANN204
        return f"From {self._origin} to {self._destination}"
