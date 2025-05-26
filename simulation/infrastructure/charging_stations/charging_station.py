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
        "_current_queue_time",
    )

    exposes = ["_location", "_plugs", "_current_queue_time"]

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
        self._current_queue_time = 0
        
        # live visualization
        self._utilization = 0

        # Events
        self._vehicle_plugged_in = self._env.event()
        self._vehicle_unplugged = self._env.event()

        # and Locks for parallel access
        self._plug_in_lock = simpy.Resource(self._env, capacity=1)
        self._plug_out_lock = simpy.Resource(self._env, capacity=1)

        # List of listening entities for the above events, in case of massive parallel access of competing fleets
        self._event_subscribers = []

        self._env.process(self.calc_current_queue_time())

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
    def current_queue_time(self):
        return self._current_queue_time

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

    def calc_current_queue_time(self):
        # a charging station could expose the current expected queue time (if a vehicle would request charging right now) from the remaining charging times of vehicles in it and requests in the queue
        while True:
            yield self._env.timeout(1)
            # first we get the most trivial scenario out of the way
            if len(self._plugs.users) < self._capacity:
                self._current_queue_time = 0
                continue

            yield self._env.timeout(
                1e-6
            )  # this might be necessary for process order, when charging tasks are making the switch from queue to plugs

            # that seems really hacky but the only way to directly access the caller that initiated the request to the simpy ressource, if you find a better way feel free to raise a pull request :)
            ongoing_charging_tasks = [
                x.proc._generator.gi_frame.f_locals["self"] for x in self._plugs.users
            ]
            queued_tasks = [
                x.proc._generator.gi_frame.f_locals["self"] for x in self._plugs.queue
            ]

            ongoing_tasks_completion_time_asc = sorted(
                [
                    x._estimated_completion_time
                    for x in ongoing_charging_tasks
                    if x._estimated_completion_time is not None
                ]
            )
            queued_tasks_charging_time = [x.charging_duration for x in queued_tasks]

            # calculate rolling finish times
            finish_times = (
                ongoing_tasks_completion_time_asc.copy()
            )  # init for currently charging
            for i, charging_time in enumerate(queued_tasks_charging_time):
                if i < self._capacity:
                    # if the queue is short, the queued vehicles finish time is just the end time of the i-th next finished vehicle plus its own charging time
                    finish_times[i] += charging_time
                else:
                    # if multiple vehicles need to rotate from the queue we need to cumulate the waiting times
                    earliest_finish_time = min(finish_times)
                    finish_times[finish_times.index(earliest_finish_time)] = (
                        earliest_finish_time + charging_time
                    )

            # the current queue time for a new vehicle is then the difference between the earliest possible finish time and the current time
            self._current_queue_time = min(finish_times) - self._env.now

    def dump(self, exposed_only: bool = True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            return {x: self.get(x) for x in self.__slots__}

    def __str__(self):
        return f"ID: {self._id}, Location: {self._location}, Current Users: {len(self._plugs.users)}, Current Queue Size: {len(self._queue)}"
