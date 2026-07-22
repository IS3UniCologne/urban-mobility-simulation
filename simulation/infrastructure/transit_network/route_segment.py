"""Segment of a public transit route between two consecutive stops."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.infrastructure.transit_network.stop import Stop


class RouteSegment:
    """Directed connection between two consecutive transit stops.

    Parameters
    ----------
    segment_id : int
        Route-local index of the segment.
    start : Stop
        Origin stop.
    end : Stop
        Destination stop.
    distance : float
        Segment length in metres.
    """

    __slots__ = ("_distance", "_end", "_segment_id", "_start")

    def __init__(
        self, segment_id: int, start: Stop, end: Stop, distance: float
    ) -> None:
        self._segment_id = segment_id
        self._start = start
        self._end = end
        self._distance = distance
        # TODO: shape ?

    @property
    def start(self) -> Stop:
        """Origin stop."""
        return self._start

    @property
    def destination(self) -> Stop:
        """Destination stop of the route segment.

        Same as end, but needed to avoid extra checks in Vehicle.
        TODO: Create common interface for this.
        """
        return self._end

    @property
    def end(self) -> Stop:
        """Destination stop."""
        return self._end

    @property
    def distance(self) -> float:
        """Segment length in metres."""
        return self._distance

    @property
    def segment_id(self) -> int:
        """Route-local segment index."""
        return self._segment_id

    def __add__(self, other: object) -> float:
        """Sum this segment's distance with another segment's."""
        if isinstance(other, RouteSegment):
            return self._distance + other._distance
        else:
            raise TypeError(
                f"{other} is not a RouteSegment object, can't sum these two together"
            )

    def __radd__(self, other: float) -> float:
        """Support summation with a numeric accumulator (e.g. sum())."""
        return other + self._distance
