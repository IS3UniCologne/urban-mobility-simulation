import logging
from abc import ABC, abstractmethod

from simpy import Environment

from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge
from tracking.tracking_interface import TrackingInterface


class VehicleState:
    # because we can't mixin an enum into an enum, we use a object-based mixin
    INITIALIZED = 0
    PARKING = 1
    DRIVING = 2
    RELOCATING = 3
    CHARGING = 4
    PRE_SERVICE = 5
    ONLINE = 6  # When the driver is online
    OFFLINE = 7  # When the driver is offline
    SOME_STATE = 1002
    RESERVED = 1001
    MOVING_TO_PICK_UP_POS = 1003


class Vehicle(TrackingInterface, ABC):
    vehicle_id = 0
    vehicle_type: str

    __slots__ = ("_id", "_state", "_env", "_position", "_position_changed")

    exposes = ["_id", "_state", "position"]

    def __init__(self, env: Environment, position):
        self._id = Vehicle.vehicle_id
        Vehicle.vehicle_id += 1  # Increment Vehicle Id
        self._env = env
        self._position = position

        # Vehicle Distance Traveled
        self._vdt = 0

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
    def position(self, position: Position):
        self._vdt += self._position >> position

        self._position = position

        self._position_changed.succeed(self._position)
        self._position_changed = self._env.event()

        logging.debug(
            f"Position updated {self._position}. VDT increased to {self._vdt}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def dump(self, exposed_only=True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            return {x: self.get(x) for x in self.__slots__}

    # Methods
    @abstractmethod
    def move(self, route_segment: Edge):
        pass

    @abstractmethod
    def __str__(self):
        pass

    def __repr__(self) -> str:
        return self.__str__()
