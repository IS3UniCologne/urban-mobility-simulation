from enum import Enum

import logging
from simpy import Environment

from .vehicle import Vehicle, VehicleState


class SharedVehicleState(VehicleState, Enum):
    SOME_STATE = 1002

class SharedVehicle(Vehicle):
    shared_vehicle_id = 0

    def __init__(self, env: Environment, position,  max_available_seats = 1, velocity = 166.7):
        super(SharedVehicle, self).__init__(env, position, max_available_seats, max_available_seats, velocity)
        self._id = SharedVehicle.shared_vehicle_id
        SharedVehicle.shared_vehicle_id += 1

    def start_driving(self):
        self.state = SharedVehicleState.DRIVING

        logging.debug(f'Driving started.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def stop_driving(self):
        self.state = SharedVehicleState.PARKING

        logging.debug(f'Driving stopped.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def park(self):
        self.state = SharedVehicleState.PARKING

        logging.debug(f'Parked.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    @property
    def id(self):
        return self._id

    def __str__(self):
        return f'I have {len(self.available_seats)} passengers on boards'