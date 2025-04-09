from simulation.environment.geodesic_position import GeodesicPosition


class Stop(GeodesicPosition):
    __slots__ = ("_stop_id", "_gtfs_id", "_departure", "_departure_next_day")

    def __init__(
        self, stop_id, gtfs_id, latitude, longitude, departure, departure_next_day: bool
    ):
        super(Stop, self).__init__(latitude, longitude)

        self._stop_id = stop_id
        self._gtfs_id = gtfs_id
        self._departure = departure
        self._departure_next_day = departure_next_day

    @property
    def stop_id(self):
        return self._stop_id

    @property
    def gtfs_id(self):
        return self._gtfs_id

    @property
    def departure(self):
        return self._departure

    @property
    def departure_next_day(self):
        return self._departure_next_day
