from simulation.environment.geodesic_position import GeodesicPosition


class Stop(GeodesicPosition):
    __slots__ = ("_departure", "_departure_next_day", "_gtfs_id", "_stop_id")

    def __init__(  # noqa: ANN204
        self,
        stop_id,  # noqa: ANN001
        gtfs_id,  # noqa: ANN001
        latitude,  # noqa: ANN001
        longitude,  # noqa: ANN001
        departure,  # noqa: ANN001
        departure_next_day: bool,
    ):
        super(Stop, self).__init__(latitude, longitude)  # noqa: UP008

        self._stop_id = stop_id
        self._gtfs_id = gtfs_id
        self._departure = departure
        self._departure_next_day = departure_next_day

    @property
    def stop_id(self):  # noqa: ANN201
        return self._stop_id

    @property
    def gtfs_id(self):  # noqa: ANN201
        return self._gtfs_id

    @property
    def departure(self):  # noqa: ANN201
        return self._departure

    @property
    def departure_next_day(self):  # noqa: ANN201
        return self._departure_next_day
