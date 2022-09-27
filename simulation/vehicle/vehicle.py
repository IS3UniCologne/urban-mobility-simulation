from abc import ABC, abstractmethod
from enum import Enum

from simpy import Environment

from simulation.agent.agent import Agent

import logging
from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge


class VehicleState():
    # because we can't mixin an enum into an enum, we use a object-based mixin
    INITIALIZED = 0
    PARKING = 1
    DRIVING = 2
    RELOCATING = 3
    CHARGING = 4
    PRE_SERVICE = 5 # Marked for Service Tasks


class Vehicle(ABC):
    vehicle_id = 0

    def __init__(self, env: Environment, position):
        self._id = Vehicle.vehicle_id
        Vehicle.vehicle_id += 1  # Increment Vehicle Id
        self._env = env
        self._position = position

        # Spatial Events
        self._position_changed = self._env.event()

        # Initial State
        self._state = VehicleState.INITIALIZED

    # Properties
    @property
    def id(self):
        return self._id

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, position : Position):
        self._position = position

        self._position_changed.succeed(self._position)
        self._position_changed = self._env.event()

        logging.debug(f'Position updated {self._position}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    # Methods
    @abstractmethod
    def move(self, route_segment: Edge):
        pass

    @abstractmethod
    def __str__(self):
        pass
