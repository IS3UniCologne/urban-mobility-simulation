from simulation.infrastructure.charging_stations.charging_station import ChargingStation


class VirtualChargingStation:
    __slots = (
        "_env",
        "_capacity",
        "_polygon",
        "_centre",
        "_plugs",
        "_id",
        "_location",
        "_power",
        "_queue",
    )

    def __init__(self, charging_station: ChargingStation):
        self._env = charging_station._env
        self._capacity = charging_station.capacity
        self._polygon = charging_station.polygon
        self._centre = [self._polygon.centroid.y, self._polygon.centroid.x]
        self._plugs = charging_station.plugs
        self._id = charging_station._id
        self._location = charging_station.location
        self._power = charging_station.power
        self._queue = charging_station._queue

    def update_capacity(self, capacity):
        self._capacity = capacity

    @property
    def capacity(self):
        return self._capacity

    @property
    def plugs(self):
        return self._plugs

    @property
    def power(self):
        return self._power

    @property
    def centre(self):
        return self._centre

    @property
    def id(self):
        return self._id

    @property
    def location(self):
        return self._location

    @property
    def polygon(self):
        return self._polygon
