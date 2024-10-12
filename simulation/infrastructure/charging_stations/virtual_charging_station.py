from typing import Optional, Tuple

from simulation.infrastructure.charging_stations.charging_station import ChargingStation


class VirtualChargingStation:
    __slots = (
        "_env",
        "_valid_timeframe",
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
        self._physical_charging_station = charging_station
        self._valid_timeframe = None
        self._capacity = charging_station.capacity
        self._polygon = charging_station.polygon
        self._centre = charging_station.centre
        self._plugs = charging_station.plugs  # reference, mutable object
        self._id = charging_station._id
        self._location = charging_station.location
        self._power = charging_station.power
        self._queue = charging_station._queue
        self._queue_size = charging_station._queue_size

    def plug_in_notify(self):
        self._physical_charging_station.plug_in_notify()

    def plug_out_notify(self):
        self._physical_charging_station.plug_out_notify()

    def update_capacity(self, capacity, valid_timeframe: Optional[Tuple[float, float]]):
        self._capacity = capacity
        self._valid_timeframe = valid_timeframe

    @property
    def valid_timeframe(self):
        return self._valid_timeframe

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

    @property
    def queue_size(self):
        return self._queue_size
