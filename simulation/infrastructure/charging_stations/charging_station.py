import h3
import simpy
from shapely.geometry import shape

from simulation.environment.geodesic_position import GeodesicPosition
from tracking.tracking_interface import TrackingInterface


class ChargingStation(TrackingInterface):
    __slots__ = (
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

    exposes = ["_location", "_plugs"]

    def __init__(
        self,
        id: int,
        env: simpy.Environment,
        location: str,
        power: float,
        capacity: int,
    ):
        self._env = env
        self._capacity = int(capacity)
        self._polygon = shape(
            {
                "type": "Polygon",
                "coordinates": [h3.h3_to_geo_boundary(location, geo_json=True)],
                "properties": "",
            }
        )
        self._centre = GeodesicPosition(
            self._polygon.centroid.y, self._polygon.centroid.x
        )
        self._plugs = simpy.PriorityResource(self._env, capacity=capacity)
        self._id = id
        self._location = location
        self._power = float(power)  # kwh/hr
        self._queue = []
        # self.position = self.location.find_zone(zones)

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

    def dump(self, exposed_only: bool = True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            return {x: self.get(x) for x in self.__slots__}
