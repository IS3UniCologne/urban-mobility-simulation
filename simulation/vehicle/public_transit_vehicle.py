from abc import ABC, abstractmethod
from enum import Enum

import logging
from simpy import Environment

from .interfaces.passenger_interface import PassengerInterface
from .vehicle import Vehicle, VehicleState
from simulation.infrastructure.route import PublicTransitRoute
from simulation.infrastructure.transit_network.stop import Stop
from ..helper.time import SimulationTimeConverter


class PublicTransitVehicleState(VehicleState, Enum):
    AT_TERMINAL_ORIGIN = 2001
    AT_TERMINAL_DESTINATION = 2002
    AT_STOP = 2003
    UNKNOWN = 2999


class PublicTransitVehicle(Vehicle, ABC):
    public_transit_vehicle_id = 0

    def __init__(self, env: Environment, route: PublicTransitRoute, position,  max_available_seats = 100, velocity = 833.5):
        super(PublicTransitVehicle, self).__init__(env, position)

        self._id = PublicTransitVehicle.public_transit_vehicle_id
        self._route = route
        self._available_seats = max_available_seats
        self._max_available_seats = max_available_seats
        self._seats = []
        self._velocity = velocity   # meter per minute (16.67m/min = 1kmh)
        self._current_stop = route.origin
        self._delay = 0 # in seconds from planned route timetable

        # Events
        self._user_mounted = self._env.event()
        self._user_unmounted = self._env.event()

        # Initialize state
        self._state = PublicTransitVehicleState.AT_TERMINAL_ORIGIN

        PublicTransitVehicle.public_transit_vehicle_id +=1

        logging.debug(f"Initialized.", extra={"clazz": self.__class__.__name__, "oid": self._id})

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

    @property
    def available_seats(self):
        return self._available_seats

    def mount_passenger(self, passenger: PassengerInterface):
        if len(self._seats) < self._available_seats:
            self._seats.append(passenger)
            self._available_seats -= 1

            self._user_mounted.succeed()
            self._user_mounted = self._env.event()

            logging.debug(f'Passenger: {passenger.identify_passenger()} mounted vehicle.',
                          extra={"clazz": self.__class__.__name__, "oid": self._id})

        elif passenger in self._seats:
            raise Exception('Passenger is already in vehicle.')
        else:
            raise Exception('Vehicle is full.')

    def unmount_passenger(self, passenger: PassengerInterface):
        if passenger in self._seats:
            self._seats.remove(passenger)
            self._available_seats += 1

            self._user_unmounted.succeed()
            self._user_unmounted = self._env.event()

            logging.debug(f'Passenger: {passenger.identify_passenger()} unmounted vehicle.',
                          extra={"clazz": self.__class__.__name__, "oid": self._id})
        else:
            raise Exception('Passenger is not in vehicle.')

    def prognose_arrival(self, stop: Stop):
        # TODO: this is pretty optimistic: What if the vehicle waits at intermediate stops

        distance = self._route.subroute(self._current_stop, stop).total_distance()
        duration = distance / self._velocity # in minutes
        arrival = SimulationTimeConverter.as_str(self._env.now + duration, '%H:%M:%S')
        # stop will likely be reached in travel duration + delay, but not earlier than planned (will wait there)
        return max(arrival, stop.departure)
