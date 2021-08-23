from abc import ABC, abstractmethod
from enum import Enum

import logging
from simpy import Environment

from .vehicle import Vehicle, VehicleState
from simulation.infrastructure.route import PublicTransitRoute
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.infrastructure.transit_network.stop import Stop
from simulation.environment.geodesic_position import GeodesicPosition


class PublicTransitVehicleState(VehicleState, Enum):
    AT_TERMINAL_ORIGIN = 2001
    AT_TERMINAL_DESTINATION = 2002
    AT_STOP = 2003
    UNKNOWN = 2999


class PublicTransitVehicle(Vehicle, ABC):
    public_transit_vehicle_id = 0

    def __init__(self, env: Environment, route: PublicTransitRoute, position,  max_available_seats = 100, velocity = 833.5):
        super(PublicTransitVehicle, self).__init__(env, position)

        self._route = route
        self._available_seats = max_available_seats
        self._max_available_seats = max_available_seats
        self._seats = []
        self._velocity = velocity   # meter per minute (16.67m/min = 1kmh)

        self._id = PublicTransitVehicle.public_transit_vehicle_id
        self._current_stop = None
        self._state = PublicTransitVehicleState.AT_TERMINAL_ORIGIN
        PublicTransitVehicle.public_transit_vehicle_id +=1

    @property
    def current_stop(self):
        return self._current_stop

    @current_stop.setter
    def current_stop(self, stop: Stop):
        self._current_stop = stop
