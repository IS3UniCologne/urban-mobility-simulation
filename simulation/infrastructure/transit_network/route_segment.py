from simulation.infrastructure.transit_network.stop import Stop


class RouteSegment:
    __slots__ = ("_segment_id", "_start", "_end", "_distance")

    def __init__(self, segment_id, start: Stop, end: Stop, distance):
        self._segment_id = segment_id
        self._start = start
        self._end = end
        self._distance = distance
        # TODO: shape ?

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    @property
    def distance(self):
        return self._distance

    @property
    def segment_id(self):
        return self._segment_id

    # '+' operator between RouteSegment Instances
    def __add__(self, other):
        if isinstance(other, RouteSegment):
            return self._distance + other._distance
        else:
            raise TypeError(
                f"{other} is not a RouteSegment object, can't sum these two together"
            )

    def __radd__(self, other):
        return other + self._distance
