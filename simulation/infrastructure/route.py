from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from simulation.helper.time import SimulationTimeConverter
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.environment.position import Position
    from simulation.infrastructure.transit_network.route_segment import RouteSegment
    from simulation.infrastructure.transit_network.stop import Stop


class Route:  # noqa: D101
    __slots__ = ("_destination", "_distance", "_origin", "_route_segments")

    def __init__(self, origin: Position, destination: Position):  # noqa: ANN204
        self._origin = origin
        self._destination = destination
        self._route_segments: list[Edge] = []
        self._distance = None

        distance = origin << destination  # euclidean distance
        self._route_segments.append(
            Edge(distance, Vertex(origin), Vertex(destination))
        )  # Append Dummy Edge

    @property
    def origin(self):  # noqa: ANN201, D102
        return self._origin

    @property
    def destination(self):  # noqa: ANN201, D102
        return self._destination

    @property
    def route_segments(self):  # noqa: ANN201, D102
        return self._route_segments

    @property
    def distance(self):  # noqa: ANN201, D102
        if self._distance is None:
            self._distance = sum(rs.distance for rs in self.route_segments)
        return self._distance

    def __str__(self) -> str:  # noqa: D105
        return f"Route(origin={self._origin}, destination={self._destination}, distance={self.distance})"

    def __repr__(self) -> str:  # noqa: D105
        return self.__str__()


class PublicTransitRoute(Route):
    """
    A PublicTransitRoute is describes deterministically by its (terminal) stops, trip segments, and
    Stop and trip segment id's are incrementally assigned and non-GTFS e.g.:
    Stop 0 -> Route Segment 0 -> Stop 1 -> ... -> Route Segment N-1 -> Stop N

    For added coherence, stops have added their GTFS id as well.
    The PublicTransitRoute id itself is the GTFS route id.
    The PublicTransitRoute trip_id is the GTFS trip id

    Naming:
    - A "route" is the spatial definition of a bus line / its driving path through stops and route segments
    - A "trip" is a special instantiation of the route through departure times
    - A "stop" is a waypoint in a route
    - A "route segment" is the part of the route between two stops
    """  # noqa: D205, D400

    def __init__(  # noqa: ANN204
        self,
        origin: GeodesicPosition,
        destination: GeodesicPosition,
        route_id: str,
        trip_id: str,
        stops: list[Stop] | None = None,
        segments: list[RouteSegment] | None = None,
    ):
        super(PublicTransitRoute, self).__init__(origin, destination)  # noqa: UP008

        self._id = route_id
        self._trip_id = trip_id
        self._trips = None

        if stops is None:
            self._route_stops: list[Stop] = []
        else:
            self._route_stops = stops
        if segments is None:
            self._route_segments: list[RouteSegment] = []
        else:
            self._route_segments = segments

    @property
    def trip_id(self) -> str:  # noqa: D102
        return self._trip_id

    @property
    def origin(self) -> GeodesicPosition:  # noqa: D102
        return self._origin

    @property
    def destination(self) -> GeodesicPosition:  # noqa: D102
        return self._destination

    @property
    def route_segments(self) -> list[RouteSegment]:  # noqa: D102
        return self._route_segments

    def add_route_segment(self, segment: RouteSegment) -> None:  # noqa: D102
        self._route_segments.append(segment)
        self._distance = None

    def route_segment_by_id(self, id: int) -> RouteSegment:  # noqa: D102
        return self._route_segments[id]

    @property
    def route_stops(self) -> list[Stop]:  # noqa: D102
        return self._route_stops

    def route_stop_by_id(self, id: int) -> Stop:  # noqa: D102
        return self._route_stops[id]

    def route_stop_by_gtfs_id(self, gtfs_id: str) -> Stop:  # noqa: D102
        # TODO: this is stupid
        for s in self._route_stops:
            if s.gtfs_id == gtfs_id:
                return s

    def add_route_stop(self, stop: Stop) -> None:  # noqa: D102
        self._route_stops.append(stop)

    def subroute(self, start: Stop, end: Stop) -> PublicTransitRoute:
        """
        Attention: The PublicTransitRoute that is returned does not adhere to index = stop ID!
        This is marked by the route_id being prefixed with SUB
        :param start: from which stop (incl.)
        :param end: to which stop (incl.)
        :return: PublicTransitRoute Object Stop_start -> ... -> Stop_end, which is a part of self
        """  # noqa: D205, D400
        return PublicTransitRoute(
            self._origin,
            self._destination,
            f"SUB_{self._id}",
            self._trip_id,
            self._route_stops[start.stop_id : end.stop_id + 1],
            self._route_segments[start.stop_id : end.stop_id],
        )

    def total_distance(self) -> float:  # noqa: D102
        return sum(self._route_segments)

    def planned_duration(self) -> float:  # noqa: D102
        return SimulationTimeConverter.duration_between(
            self.route_stop_by_id(0).departure,
            self.route_stop_by_id(-1).departure,
            end_next_day=True
            if (not self.route_stop_by_id(0).departure_next_day)
            and self.route_stop_by_id(-1).departure_next_day
            else False,
        )

    def __str__(self) -> str:  # noqa: D105
        return f"PublicTransitRoute with id/name {self._id} and trip id {self._trip_id}"
