import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simpy import Environment

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge
from simulation.vehicle.interfaces.passenger_interface import PassengerInterface
from tracking.tracking_interface import TrackingInterface

if TYPE_CHECKING:
    from simulation.operator.vehicle_fleet import VehicleFleet


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

    __slots__ = (
        "_id",
        "__state",
        "_env",
        "__position",
        "_position_changed",
        "_distance_travelled",
        "_current_task",
        "_current_region",
    )

    exposes = ["_id", "_state", "position", "_distance_travelled"]

    # We need to override __eq__ and __hash__ to use Vehicles in sets
    def __eq__(self, other) -> bool:
        if isinstance(other, Vehicle):
            return self._id == other._id
        return False

    def __hash__(self):
        return hash(self._id)

    def __init__(
        self,
        env: Environment,
        fleet: "VehicleFleet",
        position: Position,
        velocity: float,
        max_available_seats: int,
    ):
        self._id = Vehicle.vehicle_id
        Vehicle.vehicle_id += 1  # Increment Vehicle Id

        self._env = env
        self._fleet = fleet

        self.__position = position
        self._current_region = position.get_region_id()
        self._velocity = velocity

        # Seating information
        self._max_available_seats = max_available_seats
        self._seats = []  # TODO: rename to _passengers, maybe should be a set ?

        # Vehicle Distance Travelled
        self._distance_travelled = 0

        # Common Events
        self._position_changed = self._env.event()
        self._user_mounted = self._env.event()
        self._user_unmounted = self._env.event()

        # Initial State
        self.__state = VehicleState.INITIALIZED

        # Store current task (if any)
        self._current_task = None

        # For logging
        self._logging_extra = {"clazz": self.__class__.__name__, "oid": self._id}

        # Add vehicle to fleet
        self._fleet.register_vehicle(self)

    @property
    def id(self):
        return self._id

    @property
    def velocity(self):
        return self._velocity

    @property
    def available_seats(self):
        return self._max_available_seats - len(self._seats)

    @property
    def max_available_seats(self):
        return self._max_available_seats

    @property
    def state(self) -> VehicleState:
        """Get current state of the vehicle."""
        return self.__state

    @state.setter
    def state(self, state) -> None:
        """Set current state of the vehicle. Never change _state directly."""
        if state == self.__state:
            # No state change
            return
        # Notify fleet about state change
        self._fleet.update_vehicle_state(self, state)
        self.__state = state

    @property
    def position(self) -> GeodesicPosition:
        return self.__position

    @property
    def current_task(self):
        return self._current_task

    @property
    def fleet(self) -> "VehicleFleet":
        return self._fleet

    @property
    def current_region(self):
        return self._current_region

    @position.setter
    def position(self, position: GeodesicPosition):
        self._distance_travelled += self.__position >> position

        new_region = position.get_region_id()

        # did we change region?
        if new_region != self._current_region:
            self._fleet.update_vehicle_region(self, new_region)
            self._current_region = new_region

        self.__position = position

        self._position_changed.succeed(self.__position)
        self._position_changed = self._env.event()

        logging.debug(
            f"Position updated {self.__position}. Total distance travelled: {self._distance_travelled}.",
            extra=self._logging_extra,
        )

    # Standard mount/unmount passenger logic
    def mount_passenger(self, passenger: PassengerInterface):
        if passenger in self._seats:
            raise Exception(f"Passenger {passenger} is already in vehicle.")
        elif self.available_seats > 0:
            self._seats.append(passenger)

            self._user_mounted.succeed()
            self._user_mounted = self._env.event()

            logging.debug(
                f"Passenger: {passenger.identify_passenger()} mounted vehicle.",
                extra=self._logging_extra,
            )
        else:
            raise Exception("Vehicle is full.")

    def unmount_passenger(self, passenger: PassengerInterface):
        if passenger in self._seats:
            self._seats.remove(passenger)

            self._user_unmounted.succeed()
            self._user_unmounted = self._env.event()

            logging.debug(
                f"Passenger: {passenger.identify_passenger()} unmounted vehicle.",
                extra=self._logging_extra,
            )
        else:
            raise Exception("Agent is not in vehicle.")

        logging.debug("Driving stopped.", extra=self._logging_extra)

    def park(self):
        self.state = VehicleState.PARKING

        logging.debug("Parked.", extra=self._logging_extra)

    def dump(self, exposed_only=True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            return {x: self.get(x) for x in self.__slots__}

    # Methods
    @abstractmethod
    def move(self, route_segment: Edge):
        pass

    # As of now, this is only used with TransportTask
    # TODO: As part of the vehicle interface refactoring, this should be used to have transparency about a vehicles current task at all time
    def set_current_task(self, task):
        self._current_task = task

    @abstractmethod
    def __str__(self):
        return f"Vehicle {self._id} ({self.__class__.__name__})"

    def __repr__(self) -> str:
        return self.__str__()
