"""Route and public transit route definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.exceptions import StopNotFoundError
from simulation.helper.time import SimulationTimeConverter
from simulation.helper.types import GtfsRouteId
from simulation.infrastructure.network.edge import Edge

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.types import GtfsStopId, GtfsTripId
    from simulation.infrastructure.transit_network.route_segment import RouteSegment
    from simulation.infrastructure.transit_network.stop import Stop


class Route:
    """Route between an origin and a destination.

    Made up of route segments. Base route class is made up of a single route segment between origin and destination,
    but can be extended to more complex routes in subclasses.

    TODO: Does this cause performance overhead? Should we have a separate class for simple OD routes and more complex routes with segments?
    Current segment init feels a bit hacky. Currently the route segments also have an incombatible type in the subclass(RouteSegment vs Edge).

    Parameters
    ----------
    origin : GeodesicPosition
        Route start position.
    destination : GeodesicPosition
        Route end position.
    """

    __slots__ = ("_destination", "_distance", "_origin", "_route_segments")

    def __init__(self, origin: GeodesicPosition, destination: GeodesicPosition) -> None:
        self._origin = origin
        self._destination = destination
        self._route_segments: list[Edge] = []

        self._distance: float | None = origin << destination

    @property
    def origin(self) -> GeodesicPosition:
        """Route start position."""
        return self._origin

    @property
    def destination(self) -> GeodesicPosition:
        """Route end position."""
        return self._destination

    @property
    def route_segments(self) -> list[Edge]:
        """Segments making up the route. Lazy-initialised if not set."""
        if len(self._route_segments) == 0:
            self._route_segments.append(
                Edge(
                    distance=self.distance,
                    origin=self.origin,
                    destination=self.destination,
                )
            )
        return self._route_segments

    @property
    def distance(self) -> float:
        """Route length in metres."""
        if self._distance is None:
            self._distance = sum(rs.distance for rs in self.route_segments)
        return self._distance

    def __str__(self) -> str:
        """Return a human-readable summary of the route."""
        return f"Route(origin={self._origin}, destination={self._destination}, distance={self.distance})"

    def __repr__(self) -> str:
        """Return the route representation."""
        return self.__str__()


class PublicTransitRoute(Route):
    """Public transit route represented by its stops and trip segments.

    A route is deterministically represented by its (terminal) stops and trip
    segments. Stop and trip segment ids are incrementally assigned and non-GTFS,
    e.g. Stop 0 -> Route Segment 0 -> Stop 1 -> ... -> Route Segment N-1 -> Stop N.
    For coherence, stops also carry their GTFS id. The route id is the GTFS route
    id and the trip id is the GTFS trip id.

    Naming:

    - A "route" is the spatial definition of a bus line / its driving path
      through stops and route segments.
    - A "trip" is a special instantiation of the route through departure times.
    - A "stop" is a waypoint in a route.
    - A "route segment" is the part of the route between two stops.

    Parameters
    ----------
    origin : GeodesicPosition
        Route start position.
    destination : GeodesicPosition
        Route end position.
    route_id : GtfsRouteId
        GTFS route id.
    trip_id : GtfsTripId
        GTFS trip id.
    stops : list of Stop or None
        Initial route stops; empty if None.
    segments : list of RouteSegment or None
        Initial route segments; empty if None.
    """

    def __init__(
        self,
        origin: GeodesicPosition,
        destination: GeodesicPosition,
        route_id: GtfsRouteId,
        trip_id: GtfsTripId,
        stops: list[Stop] | None = None,
        segments: list[RouteSegment] | None = None,
    ) -> None:
        super().__init__(origin, destination)

        self._id = route_id
        self._trip_id = trip_id
        self._trips = None

        if stops is None:
            self._route_stops: list[Stop] = []
        else:
            self._route_stops = stops
        if segments is None:
            # pyrefly: ignore[bad-override-mutable-attribute], see TODO on Route
            self._route_segments: list[RouteSegment] = []
        else:
            self._route_segments = segments

        # PublicTransitRoute distance is derived from segment distances, not OD direct line.
        self._distance = None

    @property
    def trip_id(self) -> GtfsTripId:
        """GTFS trip id."""
        return self._trip_id

    @property
    def origin(self) -> GeodesicPosition:
        """Route start position."""
        return self._origin

    @property
    def destination(self) -> GeodesicPosition:
        """Route end position."""
        return self._destination

    @property
    def route_segments(self) -> list[RouteSegment]:  # pyrefly: ignore[bad-override]
        """Route segments between stops."""
        return self._route_segments

    def add_route_segment(self, segment: RouteSegment) -> None:
        """Append a segment and invalidate the cached distance."""
        self._route_segments.append(segment)
        self._distance = None

    def route_segment_by_id(self, id: int) -> RouteSegment:
        """Return the route segment at the given index."""
        return self._route_segments[id]

    @property
    def route_stops(self) -> list[Stop]:
        """Stops of the route in order."""
        return self._route_stops

    def route_stop_by_id(self, id: int) -> Stop:
        """Return the stop at the given index."""
        return self._route_stops[id]

    def route_stop_by_gtfs_id(self, gtfs_id: GtfsStopId) -> Stop:
        """Return the stop with the given GTFS id.

        Raises
        ------
        StopNotFoundError
            If no stop with the given GTFS id exists in the route.
        """
        # TODO: this is stupid
        for s in self._route_stops:
            if s.gtfs_id == gtfs_id:
                return s
        raise StopNotFoundError(f"No stop with GTFS id {gtfs_id} in route.")

    def add_route_stop(self, stop: Stop) -> None:
        """Append a stop to the route."""
        self._route_stops.append(stop)

    def subroute(self, start: Stop, end: Stop) -> PublicTransitRoute:
        """Return the part of this route between two stops (both inclusive).

        Warning: The returned route does not adhere to index = stop id; this is marked by
        the route id being prefixed with "SUB".

        Parameters
        ----------
        start : Stop
            First stop (inclusive).
        end : Stop
            Last stop (inclusive).

        Returns
        -------
        PublicTransitRoute
            Subroute Stop_start -> ... -> Stop_end, a part of this route.
        """
        return PublicTransitRoute(
            self._origin,
            self._destination,
            GtfsRouteId(f"SUB_{self._id}"),
            self._trip_id,
            self._route_stops[start.stop_id : end.stop_id + 1],
            self._route_segments[start.stop_id : end.stop_id],
        )

    def total_distance(self) -> float:
        """Total length of the route in metres."""
        return sum(s.distance for s in self._route_segments)

    def planned_duration(self) -> float:
        """Scheduled duration between the first and last stop in minutes."""
        return SimulationTimeConverter.duration_between(
            self.route_stop_by_id(0).departure,
            self.route_stop_by_id(-1).departure,
            end_next_day=True
            if (not self.route_stop_by_id(0).departure_next_day)
            and self.route_stop_by_id(-1).departure_next_day
            else False,
        )

    def __str__(self) -> str:
        """Return a human-readable summary of the transit route."""
        return f"PublicTransitRoute with id/name {self._id} and trip id {self._trip_id}"
