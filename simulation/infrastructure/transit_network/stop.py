from simulation.environment.geodesic_position import GeodesicPosition


class Stop(GeodesicPosition):
    def __init__(self, stop_id, gtfs_id, latitude, longitude):
        super(Stop, self).__init__(latitude, longitude)

        self._stop_id = stop_id
        self._gtfs_id = gtfs_id

    @property
    def stop_id(self):
        return self._stop_id

    @property
    def gtfs_id(self):
        return self._gtfs_id
