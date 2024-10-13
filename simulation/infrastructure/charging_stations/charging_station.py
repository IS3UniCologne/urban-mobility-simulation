import logging

import h3
import simpy
from shapely.geometry import shape

from simulation.environment.geodesic_position import GeodesicPosition
from tracking.tracking_interface import TrackingInterface


class ChargingStation(TrackingInterface):
    __slots__ = (
        "_env",
        "_capacity",
        "_queue_size",
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
        queue_size: int,
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
        self._queue_size = queue_size
        # self.position = self.location.find_zone(zones)

        # Events
        self._vehicle_plugged_in = self._env.event()
        self._vehicle_unplugged = self._env.event()

        # and Locks for parallel access
        self._plug_in_lock = simpy.Resource(self._env, capacity=1)
        self._plug_out_lock = simpy.Resource(self._env, capacity=1)

        # List of listening entities for the above events, in case of massive parallel access of competing fleets
        self._event_subscribers = []

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

    @property
    def vehicle_plugged_in(self):
        return self._vehicle_plugged_in

    @property
    def vehicle_unplugged(self):
        return self._vehicle_unplugged

    def register_event_subscriber(self, subscriber):
        self._event_subscribers.append(subscriber)

    def plug_in_notify(self):
        with self._plug_in_lock.request() as req:
            yield req
            self._vehicle_plugged_in.succeed()
            if self._event_subscribers:
                yield simpy.AllOf(
                    self._env,
                    [x.processed_plug_in_event for x in self._event_subscribers],
                )
                logging.debug(
                    "All listeners have processed the plug in event, resetting",
                    extra={"clazz": self.__class__.__name__, "oid": self._id},
                )
                for x in self._event_subscribers:
                    x.processed_plug_in_event = self._env.event()
            self._vehicle_plugged_in = self._env.event()

    def plug_out_notify(self):
        with self._plug_out_lock.request() as req:
            yield req
            self._vehicle_unplugged.succeed()
            if self._event_subscribers:
                yield simpy.AllOf(
                    self._env,
                    [x.processed_plug_out_event for x in self._event_subscribers],
                )
                logging.debug(
                    "All listeners have processed the plug out event, resetting",
                    extra={"clazz": self.__class__.__name__, "oid": self._id},
                )
                for x in self._event_subscribers:
                    x.processed_plug_out_event = self._env.event()

            self._vehicle_unplugged = self._env.event()

    def dump(self, exposed_only: bool = True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            return {x: self.get(x) for x in self.__slots__}

    def __str__(self):
        return f"ID: {self._id}, Location: {self._location}, Current Users: {len(self._plugs.users)}, Current Queue Size: {len(self._queue)}"
