from __future__ import annotations

import logging
from abc import ABC
from typing import TYPE_CHECKING

from simpy import Environment

from simulation.environment.position import Position
from simulation.helper.configuration.enums import VehicleMode, VehicleState
from simulation.helper.time import SimulationTimeConverter
from simulation.infrastructure.transit_network.stop import Stop
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.vehicle import Vehicle

if TYPE_CHECKING:
    from simulation.infrastructure.route import PublicTransitRoute


class PublicTransitVehicleException(Exception):
    pass


class PublicTransitVehicleFull(PublicTransitVehicleException):
    pass


class PublicTransitVehicle(Vehicle, ABC):
    __slots__ = ("_current_stop", "_delay", "_route")

    def __init__(
        self,
        env: Environment,
        route: PublicTransitRoute,
        position: Position,
        fleet: VehicleFleet,
        velocity,
        vehicle_mode: VehicleMode,
        max_available_seats,
    ):
        super(PublicTransitVehicle, self).__init__(
            env=env,
            fleet=fleet,
            position=position,
            velocity=velocity,
            vehicle_mode=vehicle_mode,
            max_available_seats=max_available_seats,
        )

        self._route = route
        self._current_stop = route.origin
        self._delay = 0  # in seconds from planned route timetable

        # Initialize state
        self.state = VehicleState.AT_TERMINAL_ORIGIN

        logging.debug(
            "Initialized.", extra={"clazz": self.__class__.__name__, "oid": self._id}
        )

    @property
    def route(self):
        return self._route

    @property
    def current_stop(self):
        return self._current_stop

    @current_stop.setter
    def current_stop(self, stop: Stop):
        self._current_stop = stop

    @property
    def delay(self):
        return self._delay

    def prognose_arrival(self, stop: Stop):
        # TODO: this is pretty optimistic: What if the vehicle waits at intermediate stops

        distance = self._route.subroute(self._current_stop, stop).total_distance()
        duration = distance / self._velocity  # in minutes
        arrival = SimulationTimeConverter.as_str(self._env.now + duration, "%H:%M:%S")
        # stop will likely be reached in travel duration + delay, but not earlier than planned (will wait there)
        return max(arrival, stop.departure)
