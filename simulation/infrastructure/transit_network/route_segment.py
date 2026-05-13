from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.infrastructure.transit_network.stop import Stop


class RouteSegment:  # noqa: D101
    __slots__ = ("_distance", "_end", "_segment_id", "_start")

    def __init__(self, segment_id, start: Stop, end: Stop, distance):  # noqa: ANN001, ANN204
        self._segment_id = segment_id
        self._start = start
        self._end = end
        self._distance = distance
        # TODO: shape ?

    @property
    def start(self) -> Stop:  # noqa: D102
        return self._start

    @property
    def destination(self) -> Stop:
        """Get the destination stop of the route segment.

        This is the same as end, but we need it to avoid extra checks in Vehicle.
        TODO: Create common interface for this.
        """
        return self._end

    @property
    def end(self) -> Stop:  # noqa: D102
        return self._end

    @property
    def distance(self) -> float:  # noqa: D102
        return self._distance

    @property
    def segment_id(self) -> int:  # noqa: D102
        return self._segment_id

    # '+' operator between RouteSegment Instances
    def __add__(self, other) -> float:  # noqa: ANN001, D105
        if isinstance(other, RouteSegment):
            return self._distance + other._distance
        else:
            raise TypeError(
                f"{other} is not a RouteSegment object, can't sum these two together"
            )

    def __radd__(self, other) -> float:  # noqa: ANN001, D105
        return other + self._distance
