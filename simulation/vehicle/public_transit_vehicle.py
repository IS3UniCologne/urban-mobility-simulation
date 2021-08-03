from abc import ABC, abstractmethod
from enum import Enum

import logging
from simpy import Environment

from .vehicle import Vehicle, VehicleState


class PublicTransitVehicleState(VehicleState, Enum):
    AT_TERMINAL_STATION = 2001
    EN_ROUTE_PLANNED = 2002
    EN_ROUTE_DETOUR = 2003


class PublicTransitVehicle(Vehicle, ABC):
    public_transit_vehicle_id = 0

    def __init__(self, env: Environment, position,  max_available_seats = 100, velocity = 833.5):
        super(PublicTransitVehicle, self).__init__(env, position, max_available_seats, max_available_seats, velocity)

        self._id = PublicTransitVehicle.public_transit_vehicle_id
        PublicTransitVehicle.public_transit_vehicle_id +=1