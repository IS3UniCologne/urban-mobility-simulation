"""Waypoint within a public transit route."""

from simulation.context.simulation_context import SimulationContext
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.types import GtfsStopId


class Stop(GeodesicPosition):
    """Geodesic waypoint in a public transit route.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    stop_id : int
        Route-local index (0-based).
    gtfs_id : GtfsStopId
        GTFS stop identifier.
    latitude : float
        Latitude in degrees.
    longitude : float
        Longitude in degrees.
    departure : str
        Scheduled departure as "%H:%M:%S" timestamp.
    departure_next_day : bool
        Whether departure falls on following day.
    """

    __slots__ = ("_departure", "_departure_next_day", "_gtfs_id", "_stop_id")

    def __init__(
        self,
        sim: SimulationContext,
        stop_id: int,
        gtfs_id: GtfsStopId,
        latitude: float,
        longitude: float,
        departure: str,
        departure_next_day: bool,
    ) -> None:
        super().__init__(sim, latitude, longitude)

        self._stop_id = stop_id
        self._gtfs_id = gtfs_id
        self._departure = departure
        self._departure_next_day = departure_next_day

    @property
    def stop_id(self) -> int:
        """Route-local stop index."""
        return self._stop_id

    @property
    def gtfs_id(self) -> GtfsStopId:
        """GTFS stop identifier."""
        return self._gtfs_id

    @property
    def departure(self) -> str:
        """Scheduled departure timestamp ("%H:%M:%S")."""
        return self._departure

    @property
    def departure_next_day(self) -> bool:
        """Whether departure falls on the following day."""
        return self._departure_next_day
