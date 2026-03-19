from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.exceptions import VehicleError
from simulation.helper.simulation_base import SimulationBase
from simulation.helper.state_machine import StateMachine
from simulation.helper.time import SimulationVelocityConverter
from simulation.helper.vehicle_states import VehicleStates

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import (
        Configuration,
        VehicleConfig,
    )
    from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
    from simulation.helper.types import RegionId
    from simulation.helper.vehicle_states import VehicleState
    from simulation.infrastructure.network.edge import Edge
    from simulation.infrastructure.route import Route
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.energy_system import EnergySystem
    from simulation.vehicle.movement_stats import MovementStats


class Vehicle(SimulationBase, ABC):
    """
    Base class for all vehicles.

    Contains common properties and methods used by all vehicles.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    fleet : VehicleFleet
        The fleet to which the vehicle belongs.
    position : GeodesicPosition
        The initial position of the vehicle.
    vehicle_config : VehicleConfig
        The vehicle configuration.
    """

    __slots__ = (
        "__position",
        "_autonomy_type",
        "_config",
        "_convenience",
        "_current_region",
        "_current_request",
        "_destination",
        "_distance_travelled",
        "_driver",
        "_driver_unmounted",
        "_energy_system",
        "_env",
        "_estimated_completion_time",
        "_fleet",
        "_id",
        "_max_available_seats",
        "_mode",
        "_passengers",
        "_position_changed",
        "_propulsion_type",
        "_seats",
        "_sim",
        "_state_machine",
        "_vehicle_relocation_finished",
        "_vehicle_type",
        "_velocity_mm",
    )

    # We need to override __eq__ and __hash__ to use Vehicles in sets
    def __eq__(self, other: object) -> bool:  # noqa: D105
        if isinstance(other, Vehicle):
            return self.uid == other.uid
        return False

    def __hash__(self) -> int:  # noqa: D105
        return hash(self.uid)

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        position: GeodesicPosition,
        vehicle_config: VehicleConfig,
    ) -> None:
        super().__init__(sim)

        self._sim = sim
        self._config: Configuration = sim.config
        self._env = sim.env

        self._fleet: VehicleFleet = fleet

        # Vehicle Position, name is intentionally mangled. Do not set directly.
        self.__position: GeodesicPosition = position
        self._current_region: RegionId = position.get_region_id()
        self._velocity_mm: float = SimulationVelocityConverter.kmh_to_meters_per_minute(
            vehicle_config.VELOCITY_KMH
        )
        self._vehicle_type: VehicleType = vehicle_config.VEHICLE_TYPE
        self._autonomy_type = vehicle_config.AUTONOMY_TYPE
        self._propulsion_type = vehicle_config.PROPULSION_TYPE

        # Energy System
        from simulation.vehicle.energy_system import create_energy_system

        self._energy_system = create_energy_system(sim, vehicle_config)

        # Seating information
        self._max_available_seats: int = vehicle_config.MAX_AVAILABLE_SEATS
        self._convenience: int = vehicle_config.CONVENIENCE
        self._passengers: list[User] = []

        # Vehicle Distance Travelled
        self._distance_travelled: float = 0

        # Driver
        self._driver: User | None = None

        # Common Events
        self._position_changed: Event = sim.env.event()
        self._driver_unmounted: Event = sim.env.event()
        self._vehicle_relocation_finished: Event = sim.env.event()

        # TODO: Do we want different valid transitions per vehicle type?
        self._state_machine: StateMachine[VehicleState] = StateMachine(
            initial_state=VehicleStates.STANDBY,
            allowed_transitions=VehicleStates.TRANSITIONS,
        )

        self._current_request: None | TransportRequest = None

        # Predicted state tracking for task completion
        self._estimated_completion_time: float = 0
        self._destination: GeodesicPosition | None = None

        # Add self to fleet
        self._fleet.register_vehicle(self)

    @property
    def vehicle_type(self) -> VehicleType:
        """Get the mode of the vehicle.

        Returns
        -------
        VehicleMode
            The type of the vehicle. E.g. CAR, BIKE
        """
        return self._vehicle_type

    @property
    def autonomy_type(self) -> AutonomyType:
        """Get the autonomy type of the vehicle.

        Returns
        -------
        AutonomyType
            The autonomy type of the vehicle. E.g. HUMAN_DRIVEN, AUTONOMOUS
        """
        return self._autonomy_type

    @property
    def propulsion_type(self) -> PropulsionType:
        """Get the propulsion type of the vehicle.

        Returns
        -------
        PropulsionType
            The propulsion type of the vehicle.  E.g. BATTERY_ELECTRIC, INTERNAL_COMBUSTION
        """
        return self._propulsion_type

    @property
    def energy_system(self) -> EnergySystem:
        """Get the energy system of the vehicle.

        Returns
        -------
        EnergySystem
            The energy system of the vehicle.
        """
        return self._energy_system

    @property
    def velocity(self) -> float:
        """Get the velocity of the vehicle.

        Returns
        -------
        float
            The velocity of the vehicle.
        """
        return self._velocity_mm

    def calculate_travel_time(self, distance: float) -> float:
        """Calculate travel time for a given distance.

        Parameters
        ----------
        distance : float
            Distance in meters.

        Returns
        -------
        float
            Travel time in minutes.
        """
        return distance / self._velocity_mm

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
        """Current vehicle state (read-only).

        Returns
        -------
        VehicleState
            The current state of the vehicle.
        """
        return self._state_machine.current_state

    def is_in_state_or_ancestor(self, category: VehicleState) -> bool:
        """Check if vehicle is in state or state is descendant of category.

        Parameters
        ----------
        category : VehicleState
            Category state (potential ancestor) to check.

        Returns
        -------
        bool
            True if vehicle is in category or a descendant of category.
        """
        return self._state_machine.is_in_state_or_descendant(category)

    def _go_online(self) -> None:
        self._set_state(VehicleStates.STANDBY)
        self.logger.debug("Going online.")

    def _go_offline(self) -> None:
        self._set_state(VehicleStates.OFFLINE)
        self.logger.debug("Going offline.")

    def _set_state(self, state: VehicleState) -> None:
        """Transition to a new state, validating and notifying fleet.

        Parameters
        ----------
        state : VehicleState
            The new state of the vehicle.
        """
        if state is self._state_machine.current_state:
            return
        old_state = self._state_machine.current_state
        self._state_machine.transition_to(state)
        self._fleet.update_vehicle_state(self, old_state, state)

    @property
    def position(self) -> GeodesicPosition:
        """Get the current position of the vehicle.

        Returns
        -------
        GeodesicPosition
            The current position of the vehicle.
        """
        return self.__position

    @position.setter
    def position(self, position: GeodesicPosition) -> None:
        old_position = self.__position

        self._distance_travelled += self.__position << position

        new_region = position.get_region_id()

        # did we change region?
        if new_region != self._current_region:
            self._fleet.update_vehicle_region(self, new_region)
            self._current_region = new_region

        self.__position = position

        self._position_changed.succeed(self.__position)
        self._position_changed = self._env.event()

        region_id = self.position.get_region_id()

        self.logger.debug(
            "Position updated from %s to %s in region %s. Total distance travelled: %s.",
            old_position,
            self.__position,
            region_id,
            self._distance_travelled,
        )

    @property
    def current_request(self) -> TransportRequest | None:
        """Get the current request of the vehicle.

        Returns
        -------
        TransportRequest or None
            The current request of the vehicle.
        """
        return self._current_request

    @property
    def fleet(self) -> VehicleFleet:
        """Get the fleet to which the vehicle belongs.

        Returns
        -------
        VehicleFleet
            The fleet to which the vehicle belongs.
        """
        return self._fleet

    @property
    def current_region(self) -> RegionId:
        """Get the current region of the vehicle.

        Returns
        -------
        RegionId
            The identifier of the current region of the vehicle. (e.g., hexagon ID).
        """
        return self._current_region

    @property
    def estimated_completion_time(self) -> float:
        """Estimated completion time of the current task.

        Returns
        -------
        float
            Simulation time when current task will complete (0 if idle).
        """
        return self._estimated_completion_time

    @estimated_completion_time.setter
    def estimated_completion_time(self, estimated_completion_time: float) -> None:
        """Set the estimated completion time of the current task."""
        self._estimated_completion_time = estimated_completion_time

    @property
    def destination(self) -> GeodesicPosition | None:
        """Destination position of the current movement.

        Returns
        -------
        GeodesicPosition or None
            The destination position of the current movement (None if not moving).
        """
        return self._destination

    @destination.setter
    def destination(self, value: GeodesicPosition | None) -> None:
        self._destination = value

    def clear_predicted_state(self) -> None:
        """Clear predicted state (energy, destination, time)."""
        self._energy_system.clear_predicted_energy()
        self._estimated_completion_time = 0
        self._destination = None

    # Standard mount/unmount passenger logic
    def mount_passenger(self, passenger: User) -> None:
        """Mount a passenger to the vehicle.

        This method is used to add a passenger to the vehicle.

        Parameters
        ----------
        passenger : User
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
            self.logger.debug("Passenger: %s mounted vehicle.", passenger.uid)
        else:
            raise VehicleError(
                f"Passenger {passenger} is trying to mount full vehicle {self}."
            )

    def unmount_passenger(self, passenger: User) -> None:
        """Unmount a passenger from the vehicle.

        This method is used to remove a passenger from the vehicle.

        Parameters
        ----------
        passenger : User
            The passenger to be removed from the vehicle.

        Raises
        ------
        VehicleError
            If the passenger is not in the vehicle.
        """
        if passenger in self._passengers:
            self._passengers.remove(passenger)
            self.logger.debug("Passenger: %s unmounted vehicle.", passenger.uid)
        else:
            raise VehicleError(
                f"Trying to unmount passenger {passenger} not in vehicle {self}."
            )

        self.logger.debug("Driving stopped.")

    def _update_position(self, new_position: GeodesicPosition) -> None:
        """Update the position of the vehicle and notify driver and passengers."""
        self.position = new_position

        if self._driver:
            self._driver.on_vehicle_moved(new_position)

        for passenger in self._passengers:
            passenger.on_vehicle_moved(new_position)

        self.logger.debug(
            "Current position %s in region %s.",
            self.position,
            self.position.get_region_id(),
        )

    def mount_driver(self, driver: User) -> None:
        """Mount a driver to the vehicle.

        Parameters
        ----------
        driver : User
            The driver to mount.

        Raises
        ------
        Exception
            If the vehicle already has a driver.
        """
        if self._driver is not None:
            raise Exception(
                f"Vehicle {self.uid} has already a driver {self._driver}. Unable to mount driver."
            )

        self._driver = driver
        self._set_state(VehicleStates.DRIVING)
        self.logger.debug("Driver: %s mounted vehicle.", driver)

    def unmount_driver(self) -> None:
        """Unmount the current driver from the vehicle.

        Raises
        ------
        Exception
            If no driver is mounted.
        """
        if self._driver is None:
            raise Exception("Vehicle has no driver to unmount.")

        tmp_driver_id = str(self._driver)
        self._driver = None
        self._driver_unmounted.succeed()
        self._driver_unmounted = self._env.event()
        self._set_state(VehicleStates.STANDBY)
        self.logger.debug("Driver: %s unmounted vehicle.", tmp_driver_id)

    def park(self) -> None:
        """Park the vehicle.

        Clears the current request and sets state to STANDBY.
        """
        self.set_current_request(None)
        self._set_state(VehicleStates.STANDBY)

        self.logger.debug("Parked.")

    # Methods
    @abstractmethod
    def move(self, route_segment: Edge) -> Generator[Event, None, MovementStats]:
        """Move the vehicle along a route segment.

        Parameters
        ----------
        route_segment : Edge
            The route segment along which the vehicle will move.

        Returns
        -------
        MovementStats
            The statistics of the movement.
        """

    def traverse_route(self, route: Route) -> Generator[Event, None, float]:
        """
        Traverse a route and return total energy consumed.

        Parameters
        ----------
        route : Route
            The route to traverse.

        Returns
        -------
        float
            Total energy consumed during traversal.
        """
        total_energy = 0.0
        for segment in route.route_segments:
            stats = yield from self.move(segment)
            total_energy += stats.energy_consumed

        return total_energy

    # TODO: As part of the vehicle interface refactoring, this should be used to have transparency about a vehicles current request at all time
    def set_current_request(self, request: TransportRequest | None) -> None:
        """Set the current request of the vehicle.

        Parameters
        ----------
        request : TransportRequest or None
            The request to set as the current request of the vehicle.
        """
        self._current_request = request

    def __str__(self) -> str:  # noqa: D105
        return self.uid

    def __repr__(self) -> str:  # noqa: D105
        return self.__str__()
