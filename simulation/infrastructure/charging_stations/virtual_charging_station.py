from typing import Optional, Tuple, Any
from beartype import beartype
import simpy
from shapely.geometry import Polygon

from simulation.infrastructure.charging_stations.charging_station import ChargingStation
from simulation.environment.geodesic_position import GeodesicPosition


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
        "_queue_size",
        "_current_queue_time",
    )

    @beartype
    def __init__(self, charging_station: ChargingStation) -> None:
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
        self._current_queue_time = charging_station._current_queue_time

    def plug_in_notify(self) -> simpy.events.Generator:
        yield self._env.process(self._physical_charging_station.plug_in_notify())
        assert self._plugs.users == self._physical_charging_station.plugs.users

    def plug_out_notify(self) -> simpy.events.Generator:
        yield self._env.process(self._physical_charging_station.plug_out_notify())
        assert self._plugs.users == self._physical_charging_station.plugs.users

    @beartype
    def update_capacity(self, capacity: int, valid_timeframe: Optional[Tuple[float, float]]) -> None:
        self._capacity = capacity
        self._valid_timeframe = valid_timeframe

    @property
    def valid_timeframe(self) -> Optional[Tuple[float, float]]:
        return self._valid_timeframe

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def plugs(self) -> simpy.PriorityResource:
        return self._plugs

    @property
    def power(self) -> float:
        return self._power

    @property
    def centre(self) -> GeodesicPosition:
        return self._centre

    @property
    def id(self) -> int:
        return self._id

    @property
    def location(self) -> str:
        return self._location

    @property
    def polygon(self) -> Polygon:
        return self._polygon

    @property
    def queue_size(self) -> int:
        return self._queue_size

    @property
    def current_queue_time(self) -> float:
        return self._physical_charging_station.current_queue_time
