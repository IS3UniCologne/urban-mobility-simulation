"""Physical charging station with plug allocation and queue estimation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

import h3
import simpy
from shapely.geometry import Polygon

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.simulation_base import SimulationBase
from simulation.helper.time import SimulationTimeConverter

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.types import RegionId


class _PlugEventSubscriber(Protocol):
    """Listener notified when a vehicle plugs in or out."""

    processed_plug_in_event: simpy.Event
    processed_plug_out_event: simpy.Event


class _ChargingRequest(Protocol):
    """Simpy plug request with charging-task metadata."""

    estimated_completion_time: float | None
    charging_duration: float | None


class ChargingStation(SimulationBase):  # noqa: D101
    __slots__ = (
        "_capacity",
        "_centre",
        "_cs_id",
        "_current_queue_time",
        "_env",
        "_event_subscribers",
        "_hourly_prices",
        "_location",
        "_plug_in_lock",
        "_plug_out_lock",
        "_plugs",
        "_polygon",
        "_power",
        "_queue",
        "_queue_size",
        "_sim",
        "_vehicle_plugged_in",
        "_vehicle_unplugged",
    )

    def __init__(
        self,
        sim: SimulationContext,
        cs_id: int,  # ID of the charging station in relation to the charging infrastructure it belongs to
        location: RegionId,
        power: float,
        hourly_prices_per_kWh: list[float],
        capacity: int,
        queue_size: int,
    ) -> None:
        super().__init__(sim)
        self._sim = sim
        self._env = sim.env
        self._cs_id = cs_id
        self._capacity = capacity
        self._polygon = Polygon(
            [(lon, lat) for lat, lon in h3.cell_to_boundary(location)]
        )
        self._centre = GeodesicPosition(
            self._sim, self._polygon.centroid.y, self._polygon.centroid.x
        )
        self._plugs = simpy.PriorityResource(self._env, capacity=capacity)
        self._location = location
        self._power = power  # kW
        self._hourly_prices = hourly_prices_per_kWh  # EUR / kWh

        self._queue: list[object] = []
        self._queue_size = queue_size
        self._current_queue_time: float = 0.0

        # Events
        self._vehicle_plugged_in = self._env.event()
        self._vehicle_unplugged = self._env.event()

        # and Locks for parallel access
        self._plug_in_lock = simpy.Resource(self._env, capacity=1)
        self._plug_out_lock = simpy.Resource(self._env, capacity=1)

        # List of listening entities for the above events, in case of massive parallel access of competing fleets
        self._event_subscribers: list[_PlugEventSubscriber] = []

        self._env.process(self.calc_current_queue_time())

    @property
    def capacity(self) -> int:  # noqa: D102
        return self._capacity

    @property
    def cs_id(self) -> int:
        """ID of the charging station in relation to the charging infrastructure it belongs to."""
        return self._cs_id

    @property
    def plugs(self) -> simpy.PriorityResource:  # noqa: D102
        return self._plugs

    @property
    def power(self) -> float:  # noqa: D102
        return self._power

    @property
    def centre(self) -> GeodesicPosition:  # noqa: D102
        return self._centre

    @property
    def location(self) -> RegionId:  # noqa: D102
        return self._location

    @property
    def polygon(self) -> Polygon:  # noqa: D102
        return self._polygon

    @property
    def queue_size(self) -> int:  # noqa: D102
        return self._queue_size

    @property
    def current_queue_time(self) -> float:  # noqa: D102
        return self._current_queue_time

    @property
    def vehicle_plugged_in(self) -> simpy.Event:  # noqa: D102
        return self._vehicle_plugged_in

    @property
    def vehicle_unplugged(self) -> simpy.Event:  # noqa: D102
        return self._vehicle_unplugged

    @property
    def price_per_kWh(self) -> float:
        """Current price per kWh at the current hour of day."""
        return self._hourly_prices[SimulationTimeConverter.hours(self._env.now)]

    def register_event_subscriber(self, subscriber: _PlugEventSubscriber) -> None:
        """Register a listener for plug-in / plug-out events."""
        self._event_subscribers.append(subscriber)

    def plug_in_notify(self) -> Generator[Event, None, None]:
        """Signal a plug-in and await acknowledgement from subscribers.

        Yields
        ------
        simpy.Event
            Lock request, then the combined subscriber acknowledgement event.
        """
        with self._plug_in_lock.request() as req:
            yield req
            self._vehicle_plugged_in.succeed()
            if self._event_subscribers:
                yield simpy.AllOf(
                    self._env,
                    [x.processed_plug_in_event for x in self._event_subscribers],
                )
                self.logger.debug(
                    "All listeners have processed the plug in event, resetting"
                )
                for x in self._event_subscribers:
                    x.processed_plug_in_event = self._env.event()
            self._vehicle_plugged_in = self._env.event()

    def plug_out_notify(self) -> Generator[Event, None, None]:
        """Signal a plug-out and await acknowledgement from subscribers.

        Yields
        ------
        simpy.Event
            Lock request, then the combined subscriber acknowledgement event.
        """
        with self._plug_out_lock.request() as req:
            yield req
            self._vehicle_unplugged.succeed()
            if self._event_subscribers:
                yield simpy.AllOf(
                    self._env,
                    [x.processed_plug_out_event for x in self._event_subscribers],
                )
                self.logger.debug(
                    "All listeners have processed the plug out event, resetting"
                )
                for x in self._event_subscribers:
                    x.processed_plug_out_event = self._env.event()

            self._vehicle_unplugged = self._env.event()

    def calc_current_queue_time(self) -> Generator[Event, None, None]:
        """Continuously estimate the expected queue wait time.

        Yields
        ------
        simpy.Event
            One-minute timeouts that pace the recomputation loop.
        """
        # Estimate queue time from request metadata on active and queued plugs.
        while True:
            yield self._env.timeout(1)
            # first we get the most trivial scenario out of the way
            if len(self._plugs.users) < self._capacity:
                self._current_queue_time = 0.0
                continue

            yield self._env.timeout(
                1e-6
            )  # this might be necessary for process order, when charging tasks are making the switch from queue to plugs

            ongoing_requests = cast("list[_ChargingRequest]", list(self._plugs.users))
            queued_requests = cast("list[_ChargingRequest]", list(self._plugs.queue))

            ongoing_tasks_completion_time_asc = sorted(
                [
                    req.estimated_completion_time
                    for req in ongoing_requests
                    if req.estimated_completion_time is not None
                ]
            )
            queued_tasks_charging_time = [
                req.charging_duration
                for req in queued_requests
                if req.charging_duration is not None
            ]

            # calculate rolling finish times
            finish_times = (
                ongoing_tasks_completion_time_asc.copy()
            )  # init for currently charging

            if len(ongoing_requests) != len(ongoing_tasks_completion_time_asc):
                raise ValueError(
                    "Missing estimated completion time for active charging request."
                )
            if len(queued_requests) != len(queued_tasks_charging_time):
                raise ValueError(
                    "Missing charging duration for queued charging request."
                )
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

    def timeslot_end(self, scheduled_time: float | None) -> float | None:
        """Return the end of the reserved timeslot, or None if not timeslot-based.

        Parameters
        ----------
        scheduled_time : float or None
            The scheduled start time of the timeslot.

        Returns
        -------
        float or None
            None — physical charging stations are not timeslot-based.
        """
        return None

    def __str__(self) -> str:  # noqa: D105
        return f"ID: {self._id}, Location: {self._location}, Current Users: {len(self._plugs.users)}, Current Queue Size: {len(self._queue)}"
