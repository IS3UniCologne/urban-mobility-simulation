from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from simulation.helper.configuration.enums import VehicleState
from simulation.vehicle.mixins.reservable_mixin import ReservableMixin
from simulation.vehicle.movement_stats import MovementStats

from .vehicle import Vehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.position import Position
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.infrastructure.network.edge import Edge
    from simulation.operator.operations_management.service_tasks.service_task import (
        ServiceTask,
    )
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.interfaces.driver_interface import DriverInterface


class SharedVehicle(Vehicle, ReservableMixin):  # noqa: D101
    __slots__ = (
        "_available_seats",
        "_charging_station_charging_finished",
        "_charging_station_charging_started",
        "_charging_station_plugged_in",
        "_charging_station_plugged_out",
        "_driver",
        "_driver_mounted",
        "_driver_unmounted",
        "_driving_finished",
        "_driving_started",
        "_max_available_seats",
        "_max_walking_distance",
        "_price_per_minute",
        "_price_per_trip",
        "_reserved_for_user",
        "_seats",
        "_user_mounted",
        "_user_unmounted",
        "_vehicle_parked",
        "_vehicle_relocation_finished",
        "_vehicle_relocation_started",
        "_velocity",
    )

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        position: Position,
        vehicle_config: VehicleConfig,
    ) -> None:
        super().__init__(
            sim=sim, fleet=fleet, position=position, vehicle_config=vehicle_config
        )

        self._price_per_minute: float = vehicle_config.PRICE_PER_MIN
        self._price_per_trip: float = vehicle_config.PRICE_PER_TRIP
        self._driver: DriverInterface | None = None

        self._max_walking_distance: float = vehicle_config.WALKING_DISTANCE

        self._reserved_for_user: User | None = None

        #### Vehicle Events
        # Driving Events
        self._vehicle_parked: Event = self._env.event()
        self._user_mounted: Event = self._env.event()
        self._driving_started: Event = self._env.event()
        self._driving_finished: Event = self._env.event()
        self._user_unmounted: Event = self._env.event()

        self._driver_mounted: Event = self._env.event()
        self._driver_unmounted: Event = self._env.event()

        # Relocation Events
        self._vehicle_relocation_started: Event = self._env.event()
        self._vehicle_relocation_finished: Event = self._env.event()

        # Charging Events
        self._charging_station_plugged_in: Event = self._env.event()
        self._charging_station_charging_started: Event = self._env.event()
        self._charging_station_charging_finished: Event = self._env.event()
        self._charging_station_plugged_out: Event = self._env.event()

        # Initial State
        self.state: VehicleState = VehicleState.PARKING

    @property
    def price_per_minute(self) -> float:  # noqa: D102
        return self._price_per_minute

    @property
    def price_per_trip(self) -> float:  # noqa: D102
        return self._price_per_trip

    @property
    def reserved_for_user(self) -> User:  # noqa: D102
        return self._reserved_for_user

    # TODO: remove redundant properties
    # TODO : Do we even check the seats ever ?
    @property
    def max_available_seats(self) -> int:  # noqa: D102
        return self._max_available_seats

    @max_available_seats.setter
    def max_available_seats(self, max_available_seats: int) -> None:
        self._max_available_seats = max_available_seats

    @property
    def max_walking_distance(self) -> float:  # noqa: D102
        return self._max_walking_distance

    @property
    def velocity(self) -> float:  # noqa: D102
        return self._velocity_mm

    def move(self, route_segment: Edge) -> Generator[Any, Any, MovementStats]:  # noqa: D102
        distance = route_segment.distance
        velocity = self._velocity_mm
        time = distance / velocity

        if not self.energy_system.has_enough_energy(distance):
            raise RuntimeError(
                f"{self.__class__.__name__!s} {self.uid} has been tried to move but has not enough energy."
            )

        yield self._env.timeout(time)

        self._update_positions(route_segment.destination.position)
        energy_consumed = self.energy_system.consume_for_distance(distance)
        return MovementStats(
            energy_consumed=energy_consumed,
            distance_travelled=distance,
            time_taken=time,
        )

    def start_driving(self) -> None:  # noqa: D102
        self.state = VehicleState.DRIVING

        self.logger.debug("Driving started.")

    def stop_driving(self) -> None:  # noqa: D102
        self.state = VehicleState.PARKING
        self.set_current_task(None)
        self.logger.debug("Driving stopped.")

    def park(self) -> None:  # noqa: D102
        # Lift reservation
        self.release_reservation()

        # Make vehicle available for others again
        self.state = VehicleState.PARKING

        self.logger.debug("Parked.")

    def _update_positions(self, new_position: Position) -> None:
        # Update Vehicle Position
        self.position = new_position

        # Update Position of Driver
        if self._driver:
            self._driver.position = new_position

        # Update Position of Passengers
        for passenger in self._passengers:
            passenger.position = new_position

        region_id = self.position.get_region_id()

        self.logger.debug("Current position %s in region %s.", self.position, region_id)

    def mount_driver(self, driver: DriverInterface) -> None:  # noqa: D102
        if self._driver is not None:
            raise Exception(
                f"Vehicle {self.uid} has already a driver {self._driver.identify_driver()}. Unable to mount driver."
            )

        self._driver = driver
        self._driver_mounted.succeed()
        self._driver_mounted = self._env.event()

        self.state = VehicleState.DRIVING

        self.logger.debug("Driver: %s mounted vehicle.", driver.identify_driver())

    def unmount_driver(self) -> None:  # noqa: D102
        if self._driver is None:
            raise Exception("Vehicle has no driver to unmount.")

        tmp_driver_id = self._driver.identify_driver()
        self._driver = None
        self._driver_unmounted.succeed()
        self._driver_unmounted = self._env.event()

        self.state = VehicleState.PARKING

        self.logger.debug("Driver: %s unmounted vehicle.", tmp_driver_id)

    def prepare_for_service_task(self, caller: User, task: ServiceTask) -> None:  # noqa: D102
        self.state = VehicleState.PRE_SERVICE
        self.logger.debug("Marked for Service Task [%s] by %s.", task, caller)

    def relocate(
        self, route_segment: Edge, time: float, relocator: str
    ) -> Generator[Any, Any, Any]:
        """
        Relocate vehicle independent of state of charge and availability of driver
        :param route_segment:
        :param time:
        :param relocator: The exact entity (e.g., Service Worker ID) that relocated the vehicle
        :return:
        """  # noqa: D205, D400
        if self._driver is not None or self.is_reserved or len(self._passengers) > 0:
            self.logger.debug(
                "Vehicle %s has a driver. Revoke relocation task.", self.uid
            )
            # FIX: Reset state if it was marked for service
            if self.state == VehicleState.PRE_SERVICE:
                self.state = VehicleState.PARKING
            yield self._env.timeout(1)

            return

            # raise Exception(f'Vehicle {self.uid} has a driver {self._driver.identify_driver()}. Unable to relocate vehicle.')

        # Invoke event to notify listeners that relocation started
        self._vehicle_relocation_started.succeed()
        self._vehicle_relocation_started = self._env.event()

        self.state = VehicleState.RELOCATING

        yield self._env.timeout(time)

        # Save old position for logging purposes
        old_position = self.position

        # Update new position of vehicle
        self._update_positions(route_segment.destination.position)

        # Invoke event to notify listeners that relocation ended
        self._vehicle_relocation_finished.succeed()
        self._vehicle_relocation_finished = self._env.event()

        self.state = VehicleState.PARKING

        self.logger.debug(
            "Vehicle relocated by %s from %s to %s in %s minutes.",
            relocator,
            old_position,
            self.position,
            time,
        )

    def plug_to_charging_station(self) -> None:  # noqa: D102
        self.state = VehicleState.CHARGING

        self._charging_station_plugged_in.succeed()
        self._charging_station_plugged_in = self._env.event()

        self.logger.debug("Vehicle plugged in to charging station.")

    def unplug_from_charging_station(self):  # noqa: ANN201, D102
        self.state = VehicleState.PARKING

        self._charging_station_plugged_out.succeed()
        self._charging_station_plugged_out = self._env.event()

        self.logger.debug("Vehicle plugged out from charging station.")

    def charge(self, charging_time: float, amount: int = 0) -> Generator[Any, Any, Any]:  # noqa: D102
        # TODO: This should be somewhere else. Either the base class or energy system or a dedicated component.

        # Notify charging
        self._charging_station_charging_started.succeed()
        self._charging_station_charging_started = self._env.event()

        # Delegate to energy system
        yield from self.energy_system.refill(amount, charging_time)

        # Notify charging ended
        self._charging_station_charging_finished.succeed()
        self._charging_station_charging_finished = self._env.event()

        self.logger.debug(
            "Vehicle charged %s (units) and has now %s out of %s.",
            amount,
            self.energy_system.current_energy_absolute,
            self.energy_system.capacity,
        )

    def __str__(self):  # noqa: ANN204, D105
        return f"I have {self.available_seats} passengers on boards"
