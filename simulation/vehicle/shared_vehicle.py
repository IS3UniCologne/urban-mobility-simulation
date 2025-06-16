import logging
from abc import ABC
from typing import Any
from collections.abc import Generator

from simpy import Environment, Event

from simulation.agent.user import User
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.environment.position import Position
from simulation.helper.configuration.enums import VehicleMode, VehicleState
from simulation.helper.random.random_manager import RandomManager
from simulation.infrastructure.network.edge import Edge
from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
)
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.interfaces.driver_interface import DriverInterface

from .vehicle import Vehicle


class SharedVehicle(Vehicle, ABC):
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

    def __init__(  # noqa: ANN204
        self,
        env: Environment,
        fleet: VehicleFleet,
        position: GeodesicPosition,
        velocity: float,
        vehicle_mode: VehicleMode,
        max_available_seats: int = 1,
        convenience: int = 1,
        max_state_of_charge: int = 1,
        energy_consumption: float = 0.01,
        price_per_min: int = 1.0,
        price_per_trip: float = 0.0,
        driver: DriverInterface = None,
    ):
        super().__init__(
            env,
            fleet,
            position,
            velocity,
            max_available_seats,
            vehicle_mode,
            convenience,
        )

        self._price_per_minute: int = price_per_min
        self._price_per_trip: float = price_per_trip if price_per_trip else 0.0
        self._driver = None

        # State Of Charge
        self._max_state_of_charge: int = max_state_of_charge  # in kWh
        self._current_state_of_charge: float = RandomManager().uniform(
            low=0, high=max_state_of_charge, component="INITIALSOC"
        )  # in kWh

        self._energy_consumption: int = energy_consumption  # in kWh/km

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

        # Vehicle Reservation
        self._reserved_for_user: User = None

        # Driver Interface
        if driver is not None:
            self.mount_driver(driver)

    @property
    def id(self) -> int:
        return self._id

    @property
    def price_per_minute(self) -> int:
        return self._price_per_minute

    @property
    def price_per_trip(self) -> None:
        return self._price_per_trip

    @property
    def reserved_for_user(self) -> "User":
        return self._reserved_for_user

    @property
    def max_available_seats(self) -> int:
        return self._max_available_seats

    @max_available_seats.setter
    def max_available_seats(self, max_available_seats: int) -> None:
        self._max_available_seats = max_available_seats

    @property
    def max_state_of_charge(self) -> int:
        return self._max_state_of_charge

    @property
    def current_state_of_charge(self) -> float:
        return self._current_state_of_charge

    @property
    def current_relative_state_of_charge(self) -> float:
        return (
            self.current_state_of_charge / self.max_state_of_charge
            if self.max_state_of_charge != 0
            else 1
        )

    @property
    def energy_consumption(self) -> float:
        return self._energy_consumption

    @property
    def velocity(self) -> float:
        return self._velocity

    def move(self, route_segment: Edge) -> Generator[Any, Any, Any]:
        distance = route_segment.distance
        velocity = self._velocity
        time = distance / velocity

        if not self.has_enough_state_of_charge(distance):
            raise RuntimeError(
                f"{self.__class__.__name__!s} {self._id} has been tried to move but has not enough state of charge."
            )

        yield self._env.timeout(time)

        self._update_positions(route_segment.destination.position)
        self._update_state_of_charge(distance)

    def start_driving(self) -> None:
        self.state = VehicleState.DRIVING

        logging.debug(
            "Driving started.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def stop_driving(self) -> None:
        self.state = VehicleState.PARKING
        self.set_current_task(None)
        logging.debug(
            "Driving stopped.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def park(self) -> None:
        # Lift reservation
        self._reserved_for_user = None

        # Make vehicle available for others again
        self.state = VehicleState.PARKING

        logging.debug(
            "Parked.", extra={"clazz": self.__class__.__name__, "oid": self._id}
        )

    def reserve(self, user: "User") -> None:
        self.state = VehicleState.RESERVED

        self._reserved_for_user = user

        logging.debug(
            "Reserved to %s.",
            user.id,
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def has_enough_state_of_charge(self, distance: float) -> bool:
        """
        Check if vehicle has enough SoC left for trip
        :param distance: in meter
        :return:
        """
        # Bike does not need to check SoC
        if self._mode == VehicleMode.Bike:
            return True

        if self.energy_consumption * distance / 1000 >= self._current_state_of_charge:
            return False
        return True

    def _update_state_of_charge(self, distance: float) -> None:
        """
        Update state of charge of vehicles based on driven distance.
        SoC = SoC_old - EnergyConsumption (kWh/km) * km
        :param distance: Distance driven
        """
        energy_consumed = self.energy_consumption * distance / 1000
        self._current_state_of_charge -= energy_consumed

        if self._current_state_of_charge < 0:
            self._current_state_of_charge = 0.0

        logging.debug(
            "Current state of charge %s/%s (%s%%).",
            round(self.current_state_of_charge, 2),
            self.max_state_of_charge,
            round(self.current_state_of_charge / self.max_state_of_charge * 100, 2),
            extra={"clazz": self.__class__.__name__, "oid": self._id},
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

        logging.debug(
            "Current position %s in region %s.",
            self.position,
            region_id,
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def mount_driver(self, driver: DriverInterface) -> None:
        if self._driver is not None:
            raise Exception(
                f"Vehicle {self._id} has already a driver {self._driver.identify_driver()}. Unable to mount driver."
            )

        self._driver = driver
        self._driver_mounted.succeed()
        self._driver_mounted = self._env.event()

        self.state = VehicleState.DRIVING

        logging.debug(
            "Driver: %s mounted vehicle.",
            driver.identify_driver(),
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def unmount_driver(self) -> None:
        if self._driver is None:
            raise Exception("Vehicle has no driver to unmount.")

        tmp_driver_id = self._driver.identify_driver()
        self._driver = None
        self._driver_unmounted.succeed()
        self._driver_unmounted = self._env.event()

        self.state = VehicleState.PARKING

        logging.debug(
            "Driver: %s unmounted vehicle.",
            tmp_driver_id,
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def prepare_for_service_task(self, caller: "User", task: "ServiceTask") -> None:
        self.state = VehicleState.PRE_SERVICE
        logging.debug(
            "Marked for Service Task [%s] by %s.",
            task,
            caller,
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def relocate(
        self, route_segment: Edge, time: float, relocator: str
    ) -> Generator[Any, Any, Any]:
        """
        Relocate vehicle independent of state of charge and availability of driver
        :param route_segment:
        :param time:
        :param relocator: The exact entity (e.g., Service Worker ID) that relocated the vehicle
        :return:
        """
        if (
            self._driver is not None
            or self.state == VehicleState.RESERVED
            or len(self._passengers) > 0
        ):
            logging.debug(
                "Vehicle %s has a driver. Revoke relocation task.",
                self._id,
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )

            yield self._env.timeout(1)

            return

            # raise Exception(f'Vehicle {self._id} has a driver {self._driver.identify_driver()}. Unable to relocate vehicle.')

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

        logging.debug(
            "Vehicle relocated by %s from %s to %s in %s minutes.",
            relocator,
            old_position,
            self.position,
            time,
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def plug_to_charging_station(self) -> None:
        self.state = VehicleState.CHARGING

        self._charging_station_plugged_in.succeed()
        self._charging_station_plugged_in = self._env.event()

        logging.debug(
            "Vehicle plugged in to charging station.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def unplug_from_charging_station(self):  # noqa: ANN201
        self.state = VehicleState.PARKING

        self._charging_station_plugged_out.succeed()
        self._charging_station_plugged_out = self._env.event()

        logging.debug(
            "Vehicle plugged out from charging station.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def charge(self, charging_time: float, amount: int = 0) -> Generator[Any, Any, Any]:
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

        logging.debug(
            "Vehicle charged %s kWh and has now %s kWh out of %s.",
            amount,
            self._current_state_of_charge,
            self._max_state_of_charge,
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def __str__(self) -> str:
        return f"I have {self.available_seats} passengers on boards"
