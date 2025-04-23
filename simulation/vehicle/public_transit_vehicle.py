from __future__ import annotations

import logging
from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING

from simpy import Environment, Event

from simulation.environment.position import Position
from simulation.helper.time import SimulationTimeConverter
from simulation.infrastructure.route import Route
from simulation.infrastructure.transit_network.stop import Stop
from simulation.vehicle.vehicle import Vehicle, VehicleState

if TYPE_CHECKING:
    from simulation.agent.user import TransitUser
    from simulation.infrastructure.route import PublicTransitRoute
    from simulation.environment.geodesic_position import GeodesicPosition


class PublicTransitVehicleState(VehicleState, Enum):
    AT_TERMINAL_ORIGIN = 2001
    AT_TERMINAL_DESTINATION = 2002
    AT_STOP = 2003

    # bus specific
    EN_ROUTE_PLANNED = 2011
    EN_ROUTE_DETOUR = 2012

    UNKNOWN = 2999


class PublicTransitVehicleException(Exception):
    pass


class PublicTransitVehicleFull(PublicTransitVehicleException):
    pass


class PublicTransitVehicle(Vehicle, ABC):
    public_transit_vehicle_id = 0

    def __init__(
        self,
        env: Environment,
        route: PublicTransitRoute,
        position: "GeodesicPosition",
        velocity:float,
        max_available_seats:int=100,
    ):
        super(PublicTransitVehicle, self).__init__(env, position)

        self._id:int = PublicTransitVehicle.public_transit_vehicle_id
        self._route:Route = route
        self._available_seats:int = max_available_seats
        self._max_available_seats:int = max_available_seats
        self._seats:list[int] = []
        self._velocity:float = velocity  # meter per minute (16.67m/min = 1kmh)
        self._current_stop: Position = route.origin
        self._delay:int = 0  # in seconds from planned route timetable

        # Events
        self._user_mounted: Event = self._env.event()
        self._user_unmounted: Event = self._env.event()

        # Initialize state
        self._state: VehicleState = PublicTransitVehicleState.AT_TERMINAL_ORIGIN

        PublicTransitVehicle.public_transit_vehicle_id += 1

        logging.debug(
            "Initialized.", extra={"clazz": self.__class__.__name__, "oid": self._id}
        )

    @property
    def route(self) -> Route:
        return self._route

    @property
    def current_stop(self) -> Stop:
        return self._current_stop

    @current_stop.setter
    def current_stop(self, stop: Stop) -> None:
        self._current_stop = stop

    @property
    def delay(self) -> int:
        return self._delay

    @property
    def available_seats(self) -> int:
        return self._available_seats

    def mount_passenger(self, passenger: TransitUser) -> None:
        if self._available_seats > 0:
            self._seats.append(passenger)
            self._available_seats -= 1

            self._user_mounted.succeed()
            self._user_mounted = self._env.event()

            logging.debug(
                f"Passenger: {passenger.identify_passenger()} mounted vehicle.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )

        elif passenger in self._seats:
            raise Exception("Passenger is already in vehicle.")
        else:
            raise PublicTransitVehicleFull

    def unmount_passenger(self, passenger: TransitUser) -> None:
        if passenger in self._seats:
            self._seats.remove(passenger)
            self._available_seats += 1

            self._user_unmounted.succeed()
            self._user_unmounted = self._env.event()

            logging.debug(
                f"Passenger: {passenger.identify_passenger()} unmounted vehicle.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )
        else:
            raise Exception("Passenger is not in vehicle.")

    def prognose_arrival(self, stop: Stop) -> str:
        # TODO: this is pretty optimistic: What if the vehicle waits at intermediate stops

        distance = self._route.subroute(self._current_stop, stop).total_distance()
        duration = distance / self._velocity  # in minutes
        arrival = SimulationTimeConverter.as_str(self._env.now + duration, "%H:%M:%S")
        # stop will likely be reached in travel duration + delay, but not earlier than planned (will wait there)
        return max(arrival, stop.departure)
