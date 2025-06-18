import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simpy import Environment, Event
from simulation.environment.position import Position
from simulation.helper.configuration.enums import VehicleMode, VehicleState
from simulation.infrastructure.network.edge import Edge
from simulation.tasks.transport_task import TransportTask
from simulation.vehicle.interfaces.passenger_interface import PassengerInterface
from tracking.tracking_interface import TrackingInterface

if TYPE_CHECKING:
    from simulation.operator.vehicle_fleet import VehicleFleet


class VehicleError(Exception):
    """Base class for all vehicle-related exceptions."""


class Vehicle(TrackingInterface, ABC):
    """Base class for all vehicles.

    Contains common properties and methods used by all vehicles.
    """

    vehicle_id: int = 0
    vehicle_type: str

    __slots__ = (
        "__position",
        "__state",
        "_convenience",
        "_current_region",
        "_current_task",
        "_distance_travelled",
        "_env",
        "_id",
        "_max_available_seats",
        "_mode",
        "_position_changed",
        "_seats",
        "_velocity",
    )

    exposes = ["_id", "state", "position", "_distance_travelled"]  # noqa: RUF012

    # We need to override __eq__ and __hash__ to use Vehicles in sets
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Vehicle):
            return self._id == other._id
        return False

    def __hash__(self) -> int:
        return hash(self._id)

    def __init__(
        self,
        env: Environment,
        fleet: "VehicleFleet",
        position: Position,
        velocity: float,
        max_available_seats: int,
        vehicle_mode: VehicleMode,
        convenience: int = 1,
    ) -> None:
        self._id: int = Vehicle.vehicle_id
        Vehicle.vehicle_id += 1  # Increment Vehicle Id

        self._env: Environment = env
        self._fleet: VehicleFleet = fleet

        # Vehicle Position, name is intentionally mangled. Do not set directly.
        self.__position: Position = position
        self._current_region: str = position.get_region_id()
        self._velocity: float = velocity
        self._mode: VehicleMode = vehicle_mode

        # Seating information
        self._max_available_seats: int = max_available_seats
        self._convenience: int = convenience
        self._passengers: list[PassengerInterface] = []

        # Vehicle Distance Travelled
        self._distance_travelled: float = 0

        # Common Events
        self._position_changed: Event = self._env.event()
        self._user_mounted: Event = self._env.event()
        self._user_unmounted: Event = self._env.event()

        # Initial State, name is intentionally mangled. Do not set directly.
        self.__state: VehicleState = VehicleState.INITIALIZED

        # Store current task (if any)
        # TODO: Make this a generic task interface
        self._current_task: None | TransportTask = None

        # For logging
        self._logging_extra: dict[str, str | int] = {
            "clazz": self.__class__.__name__,
            "oid": self._id,
        }

        # Add self to fleet
        self._fleet.register_vehicle(self)

    @property
    def mode(self) -> VehicleMode:
        """Get the mode of the vehicle.

        Returns
        -------
        VehicleMode
            The mode of the vehicle.
        """
        return self._mode

    @property
    def id(self) -> int:
        """Get the unique identifier of the vehicle.

        Returns
        -------
        int
            The unique identifier of the vehicle.
        """
        return self._id

    @property
    def velocity(self) -> float:
        """Get the velocity of the vehicle.

        Returns
        -------
        float
            The velocity of the vehicle.
        """
        return self._velocity

    @property
    def available_seats(self) -> int:
        """Get the number of available seats in the vehicle.

        Returns
        -------
        int
            The number of available seats in the vehicle.
        """
        return self._max_available_seats - len(self._passengers)

    @property
    def convenience(self) -> int:
        """Get the convenience level of the vehicle.

        This affects the utility of the vehicle for passengers in mode choice.
        Lower values are better.

        Returns
        -------
        int
            The convenience level of the vehicle.
        """
        return self._convenience

    @property
    def max_available_seats(self) -> int:
        """Get the maximum number of available seats in the vehicle.

        Returns
        -------
        int
            The maximum number of available seats in the vehicle.
        """
        return self._max_available_seats

    @property
    def state(self) -> VehicleState:
        """Get current state of the vehicle.

        Returns
        -------
        VehicleState
            The current state of the vehicle.
        """
        return self.__state

    @state.setter
    def state(self, state: VehicleState) -> None:
        """Set current state of the vehicle.

        DO NOT CHANGE _state DIRECTLY.
        This is to ensure that the fleet is notified of state changes.

        Parameters
        ----------
        state : VehicleState
            The new state of the vehicle.
        """
        if state == self.__state:
            # No state change
            return
        # Notify fleet about state change
        self._fleet.update_vehicle_state(self, state)
        self.__state = state

    @property
    def position(self) -> Position:
        """Get the current position of the vehicle.

        Returns
        -------
        Position
            The current position of the vehicle.
        """
        return self.__position

    @position.setter
    def position(self, position: Position) -> None:
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
            "Position updated %s. Total distance travelled: %s.",
            self.__position,
            self._distance_travelled,
            extra=self._logging_extra,
        )

    @property
    def current_task(self) -> TransportTask | None:
        """Get the current task of the vehicle.

        Returns
        -------
        TransportTask
            The current task of the vehicle.
        """
        return self._current_task

    @property
    def fleet(self) -> "VehicleFleet":
        """Get the fleet to which the vehicle belongs.

        Returns
        -------
        VehicleFleet
            The fleet to which the vehicle belongs.
        """
        return self._fleet

    @property
    def current_region(self) -> str:
        """Get the current region of the vehicle.

        Returns
        -------
        str
            The identifier of the current region of the vehicle. (e.g., hexagon ID).
        """
        return self._current_region

    # Standard mount/unmount passenger logic
    def mount_passenger(self, passenger: PassengerInterface) -> None:
        """Mount a passenger to the vehicle.

        This method is used to add a passenger to the vehicle.

        Parameters
        ----------
        passenger : PassengerInterface
            The passenger to be added to the vehicle.

        Raises
        ------
        VehicleError
            If the passenger is already in the vehicle or if the vehicle is full.
        """
        if passenger in self._passengers:
            raise VehicleError(f"Passenger {passenger} is already in vehicle.")
        elif self.available_seats > 0:
            self._passengers.append(passenger)

            self._user_mounted.succeed()
            self._user_mounted = self._env.event()

            logging.debug(
                "Passenger: %s mounted vehicle.",
                passenger.identify_passenger(),
                extra=self._logging_extra,
            )
        else:
            raise VehicleError(
                f"Passenger {passenger} is trying to mount full vehicle {self}."
            )

    def unmount_passenger(self, passenger: PassengerInterface) -> None:
        """Unmount a passenger from the vehicle.

        This method is used to remove a passenger from the vehicle.

        Parameters
        ----------
        passenger : PassengerInterface
            The passenger to be removed from the vehicle.

        Raises
        ------
        VehicleError
            If the passenger is not in the vehicle.
        """
        if passenger in self._passengers:
            self._passengers.remove(passenger)

            self._user_unmounted.succeed()
            self._user_unmounted = self._env.event()
            logging.debug(
                "Passenger: %s unmounted vehicle.",
                passenger.identify_passenger(),
                extra=self._logging_extra,
            )

        else:
            raise VehicleError(
                f"Trying to unmount passenger {passenger} not in vehicle {self}."
            )

        logging.debug("Driving stopped.", extra=self._logging_extra)

    def park(self) -> None:
        """Park the vehicle.

        This method is used to set the vehicle to a parked state.
        """
        self.state = VehicleState.PARKING

        logging.debug("Parked.", extra=self._logging_extra)

    def dump(self, exposed_only: bool = True) -> dict[str, object]:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            return {x: self.get(x) for x in self.__slots__}

    # Methods
    @abstractmethod
    def move(self, route_segment: Edge) -> None:
        """Move the vehicle along a route segment.

        Parameters
        ----------
        route_segment : Edge
            The route segment along which the vehicle will move.
        """

    # As of now, this is only used with TransportTask
    # TODO: As part of the vehicle interface refactoring, this should be used to have transparency about a vehicles current task at all time
    def set_current_task(self, task: TransportTask | None) -> None:
        """Set the current task of the vehicle.

        Parameters
        ----------
        task : TransportTask
            The task to be set as the current task of the vehicle.
        """
        self._current_task = task

    def __str__(self) -> str:
        """Return string representation of the vehicle."""
        return f"Vehicle {self._id} ({self.__class__.__name__})"

    def __repr__(self) -> str:
        """Return string representation of the vehicle."""
        return self.__str__()
