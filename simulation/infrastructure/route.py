from typing import List


from simulation.environment.geodesic_position import GeodesicPosition
from simulation.environment.position import Position
from simulation.helper.time import SimulationTimeConverter
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.infrastructure.transit_network.stop import Stop


class Route:
    __slots__ = ("_origin", "_destination", "_route_segments")

    def __init__(self, origin: Position, destination: Position):
        self._origin = origin
        self._destination = destination
        self._route_segments: List[Edge] = []

        distance = origin >> destination  # euclidean distance
        self._route_segments.append(
            Edge(distance, Vertex(origin), Vertex(destination))
        )  # Append Dummy Edge

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
    """

    def __init__(
        self,
        origin: GeodesicPosition,
        destination: GeodesicPosition,
        route_id: str,
        trip_id: str,
        stops: List[Stop] = None,
        segments: List[RouteSegment] = None,
    ):
        super(PublicTransitRoute, self).__init__(origin, destination)

        self._id = route_id
        self._trip_id = trip_id
        self._trips = None

        if stops is None:
            self._route_stops: List[Stop] = []
        else:
            self._route_stops = stops
        if segments is None:
            self._route_segments: List[RouteSegment] = []
        else:
            self._route_segments = segments

    @property
    def trip_id(self):
        return self._trip_id

    @property
    def origin(self):
        return self._origin

    @property
    def destination(self):
        return self._destination

    @property
    def route_segments(self):
        return self._route_segments

    def add_route_segment(self, segment: RouteSegment):
        self._route_segments.append(segment)

    def route_segment_by_id(self, id):
        return self._route_segments[id]

    @property
    def route_stops(self):
        return self._route_stops

    def route_stop_by_id(self, id):
        return self._route_stops[id]

    def route_stop_by_gtfs_id(self, gtfs_id):
        # TODO: this is stupid
        for s in self._route_stops:
            if s.gtfs_id == gtfs_id:
                return s

    def add_route_stop(self, stop: Stop):
        self._route_stops.append(stop)

    def subroute(self, start: Stop, end: Stop):
        """
        Attention: The PublicTransitRoute that is returned does not adhere to index = stop ID!
        This is marked by the route_id being prefixed with SUB
        :param start: from which stop (incl.)
        :param end: to which stop (incl.)
        :return: PublicTransitRoute Object Stop_start -> ... -> Stop_end, which is a part of self
        """
        return PublicTransitRoute(
            self._origin,
            self._destination,
            f"SUB_{self._id}",
            self._trip_id,
            self._route_stops[start.stop_id : end.stop_id + 1],
            self._route_segments[start.stop_id : end.stop_id],
        )

    def total_distance(self):
        return sum(self._route_segments)

    def planned_duration(self):
        return SimulationTimeConverter.duration_between(
            self.route_stop_by_id(0).departure,
            self.route_stop_by_id(-1).departure,
            end_next_day=True
            if (not self.route_stop_by_id(0).departure_next_day)
            and self.route_stop_by_id(-1).departure_next_day
            else False,
        )

    def __str__(self):
        return f"PublicTransitRoute with id/name {self._id} and trip id {self._trip_id}"
