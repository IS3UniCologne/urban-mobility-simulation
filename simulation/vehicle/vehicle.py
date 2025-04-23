import logging
from abc import ABC, abstractmethod

from simpy import Environment
from simpy.events import Event
from typing import TYPE_CHECKING, Any

from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge
from simulation.tasks.transport_task import TransportTask
from tracking.tracking_interface import TrackingInterface

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition


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
    vehicle_id: int = 0
    vehicle_type: str

    __slots__ = ("_id", "_state", "_env", "_position", "_position_changed", "_vdt", "_current_task")

    exposes = ["_id", "_state", "position", "_vdt"]

    def __init__(self, env: Environment, position: "GeodesicPosition") -> None:
        self._id: int = Vehicle.vehicle_id
        Vehicle.vehicle_id: int = self._id + 1
         # Increment Vehicle Id
        self._env: Environment = env
        self._position: "GeodesicPosition" = position

        # Vehicle Distance Traveled
        self._vdt: int = 0

        # Spatial Events
        self._position_changed: Event = self._env.event()

        # Initial State
        self._state: VehicleState = VehicleState.INITIALIZED

        # Store current task (if any)
        self._current_task: TransportTask = None

    # Properties
    @property
    def id(self) -> int:
        return self._id

    @property
    def state(self) -> VehicleState:
        return self._state

    @state.setter
    def state(self, state: VehicleState) -> None:
        self._state = state

    @property
    def position(self) -> "GeodesicPosition":
        return self._position

    @property
    def current_task(self) -> TransportTask:
        return self._current_task

    @position.setter
    def position(self, position: "GeodesicPosition") -> None:
        self._vdt += self._position >> position

        self._position = position

        self._position_changed.succeed(self._position)
        self._position_changed = self._env.event()

        logging.debug(
            f"Position updated {self._position}. VDT increased to {self._vdt}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def dump(self, exposed_only=True) -> dict[str, Any]:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            return {x: self.get(x) for x in self.__slots__}

    # Methods
    @abstractmethod
    def move(self, route_segment: Edge) -> None:
        pass

    # As of now, this is only used with TransportTask
    # TODO: As part of the vehicle interface refactoring, this should be used to have transparency about a vehicles current task at all time
    def set_current_task(self, task: TransportTask) -> None:
        self._current_task = task

    @abstractmethod
    def __str__(self) -> None: 
        pass

    def __repr__(self) -> str:
        return self.__str__()
