from simulation.context.simulation_context import SimulationContext  # noqa: D100
from simulation.environment.geodesic_position import GeodesicPosition


class Stop(GeodesicPosition):  # noqa: D101
    __slots__ = ("_departure", "_departure_next_day", "_gtfs_id", "_stop_id")

    def __init__(
        self,
        sim: SimulationContext,
        stop_id: str,
        gtfs_id: str,
        latitude: float,
        longitude: float,
        departure: float,
        departure_next_day: bool,
    ) -> None:
        super(Stop, self).__init__(sim, latitude, longitude)  # noqa: UP008

        self._stop_id = stop_id
        self._gtfs_id = gtfs_id
        self._departure = departure
        self._departure_next_day = departure_next_day

    @property
    def stop_id(self) -> str:  # noqa: D102
        return self._stop_id

    @property
    def gtfs_id(self) -> str:  # noqa: D102
        return self._gtfs_id

    @property
    def departure(self) -> float:  # noqa: D102
        return self._departure

    @property
    def departure_next_day(self) -> bool:  # noqa: D102
        return self._departure_next_day
