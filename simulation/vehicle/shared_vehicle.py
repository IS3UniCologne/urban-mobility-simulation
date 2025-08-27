from __future__ import annotations  # noqa: D100

from abc import ABC
from typing import TYPE_CHECKING, Any

from simulation.helper.configuration.enums import VehicleState, VehicleType

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


class SharedVehicle(Vehicle, ABC):  # noqa: D101
    __slots__ = (
        "_available_seats",
        "_charging_station_charging_finished",
        "_charging_station_charging_started",
        "_charging_station_plugged_in",
        "_charging_station_plugged_out",
        "_current_state_of_charge",
        "_driver",
        "_driver_mounted",
        "_driver_unmounted",
        "_driving_finished",
        "_driving_started",
        "_energy_consumption",
        "_max_available_seats",
        "_max_state_of_charge",
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

        # State Of Charge
        self._max_state_of_charge: float = vehicle_config.MAX_STATE_OF_CHARGE  # in kWh
        self._current_state_of_charge: float = sim.random_manager.uniform(
            low=0, high=self._max_state_of_charge, component="INITIALSOC"
        )  # in kWh

        self._energy_consumption: float = vehicle_config.ENERGY_CONSUMPTION  # in kWh/km

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
        self.state: VehicleState = VehicleState.PARKING

        # Vehicle Reservation
        self._reserved_for_user = None

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
    def max_state_of_charge(self) -> float:  # noqa: D102
        return self._max_state_of_charge

    @property
    def current_state_of_charge(self) -> float:  # noqa: D102
        return self._current_state_of_charge

    @property
    def current_relative_state_of_charge(self) -> float:  # noqa: D102
        return (
            self.current_state_of_charge / self.max_state_of_charge
            if self.max_state_of_charge != 0
            else 1
        )

    @property
    def energy_consumption(self) -> float:  # noqa: D102
        return self._energy_consumption

    @property
    def velocity(self) -> float:  # noqa: D102
        return self._velocity

    def move(self, route_segment: Edge) -> Generator[Any, Any, Any]:  # noqa: D102
        distance = route_segment.distance
        velocity = self._velocity
        time = distance / velocity

        if not self.has_enough_state_of_charge(distance):
            raise RuntimeError(
                f"{self.__class__.__name__!s} {self.uid} has been tried to move but has not enough state of charge."
            )

        yield self._env.timeout(time)

        self._update_positions(route_segment.destination.position)
        self._update_state_of_charge(distance)

    def start_driving(self) -> None:  # noqa: D102
        self.state = VehicleState.DRIVING

        self.logger.debug("Driving started.")

    def stop_driving(self) -> None:  # noqa: D102
        self.state = VehicleState.PARKING
        self.set_current_task(None)
        self.logger.debug("Driving stopped.")

    def park(self) -> None:  # noqa: D102
        # Lift reservation
        self._reserved_for_user = None

        # Make vehicle available for others again
        self.state = VehicleState.PARKING

        self.logger.debug("Parked.")

    def reserve(self, user: User) -> None:  # noqa: D102
        self.state = VehicleState.RESERVED

        self._reserved_for_user = user

        self.logger.debug("Reserved to %s.", user.uid)

    def has_enough_state_of_charge(self, distance: float) -> bool:
        """
        Check if vehicle has enough SoC left for trip
        :param distance: in meter
        :return:
        """  # noqa: D205, D400
        # Bike does not need to check SoC
        if self._vehicle_type == VehicleType.BIKE:
            return True

        if self.energy_consumption * distance / 1000 >= self._current_state_of_charge:
            return False
        return True

    def _update_state_of_charge(self, distance: float) -> None:
        """
        Update state of charge of vehicles based on driven distance.
        SoC = SoC_old - EnergyConsumption (kWh/km) * km
        :param distance: Distance driven
        """  # noqa: D205, D400
        energy_consumed = self.energy_consumption * distance / 1000
        self._current_state_of_charge -= energy_consumed

        if self._current_state_of_charge < 0:
            self._current_state_of_charge = 0.0

        self.logger.debug(
            "Current state of charge %s/%s (%s%%).",
            round(self.current_state_of_charge, 2),
            self.max_state_of_charge,
            round(self.current_state_of_charge / self.max_state_of_charge * 100, 2),
        )

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
        if (
            self._driver is not None
            or self.state == VehicleState.RESERVED
            or len(self._passengers) > 0
        ):
            self.logger.debug(
                "Vehicle %s has a driver. Revoke relocation task.", self.uid
            )
            # TODO: Whey are we yielding here?
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
        # Notify charging
        self._charging_station_charging_started.succeed()
        self._charging_station_charging_started = self._env.event()

        if amount == 0:
            amount = self._max_state_of_charge - self._current_state_of_charge

        # Update Current State of Charge
        self._current_state_of_charge += amount

        # Charge
        yield self._env.timeout(charging_time)

        # Notify charging ended
        self._charging_station_charging_finished.succeed()
        self._charging_station_charging_finished = self._env.event()

        self.logger.debug(
            "Vehicle charged %s kWh and has now %s kWh out of %s.",
            amount,
            self._current_state_of_charge,
            self._max_state_of_charge,
        )

    def __str__(self):  # noqa: ANN204, D105
        return f"I have {self.available_seats} passengers on boards"
        return f"I have {self.available_seats} passengers on boards"
        return f"I have {self.available_seats} passengers on boards"
        return f"I have {self.available_seats} passengers on boards"
        return f"I have {self.available_seats} passengers on boards"
        return f"I have {self.available_seats} passengers on boards"
