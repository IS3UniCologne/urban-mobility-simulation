import logging
from abc import ABC

from simpy import Environment

from simulation.environment.position import Position
from simulation.helper.configuration.enums import VehicleMode, VehicleState
from simulation.helper.random.random_manager import RandomManager
from simulation.infrastructure.network.edge import Edge
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.interfaces.driver_interface import DriverInterface

from .vehicle import Vehicle


class SharedVehicle(Vehicle, ABC):
    __slots__ = (
        "_velocity",
        "_max_available_seats",
        "_max_state_of_charge",
        "_energy_consumption",
        "_price_per_minute",
        "_price_per_trip",
        "_driver",
        "_available_seats",
        "_seats",
        "_current_state_of_charge",
        "_vehicle_parked",
        "_user_mounted",
        "_driving_started",
        "_driving_finished",
        "_user_unmounted",
        "_driver_mounted",
        "_driver_unmounted",
        "_vehicle_relocation_started",
        "_vehicle_relocation_finished",
        "_charging_station_plugged_in",
        "_charging_station_charging_started",
        "_charging_station_charging_finished",
        "_charging_station_plugged_out",
        "_reserved_for_user",
    )

    def __init__(
        self,
        env: Environment,
        fleet: VehicleFleet,
        position,
        velocity,
        vehicle_mode: VehicleMode,
        max_available_seats=1,
        convenience=1,
        max_state_of_charge=1,
        energy_consumption=0.01,
        price_per_min=1.0,
        price_per_trip=0.0,
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

        self._price_per_minute = price_per_min
        self._price_per_trip = price_per_trip if price_per_trip else 0.0
        self._driver = None

        # State Of Charge
        self._max_state_of_charge = max_state_of_charge  # in kWh
        self._current_state_of_charge = RandomManager().uniform(
            low=0, high=max_state_of_charge, component="INITIALSOC"
        )  # in kWh

        self._energy_consumption = energy_consumption  # in kWh/km

        #### Vehicle Events
        # Driving Events
        self._vehicle_parked = self._env.event()
        self._user_mounted = self._env.event()
        self._driving_started = self._env.event()
        self._driving_finished = self._env.event()
        self._user_unmounted = self._env.event()

        self._driver_mounted = self._env.event()
        self._driver_unmounted = self._env.event()

        # Relocation Events
        self._vehicle_relocation_started = self._env.event()
        self._vehicle_relocation_finished = self._env.event()

        # Charging Events
        self._charging_station_plugged_in = self._env.event()
        self._charging_station_charging_started = self._env.event()
        self._charging_station_charging_finished = self._env.event()
        self._charging_station_plugged_out = self._env.event()

        # Initial State
        self.state = VehicleState.PARKING

        # Vehicle Reservation
        self._reserved_for_user = None

        # Driver Interface
        if driver is not None:
            self.mount_driver(driver)

    @property
    def id(self):
        return self._id

    @property
    def price_per_minute(self):
        return self._price_per_minute

    @property
    def price_per_trip(self):
        return self._price_per_trip

    @property
    def reserved_for_user(self):
        return self._reserved_for_user

    @property
    def max_available_seats(self):
        return self._max_available_seats

    @max_available_seats.setter
    def max_available_seats(self, max_available_seats):
        self._max_available_seats = max_available_seats

    @property
    def max_state_of_charge(self):
        return self._max_state_of_charge

    @property
    def current_state_of_charge(self):
        return self._current_state_of_charge

    @property
    def current_relative_state_of_charge(self):
        return (
            self.current_state_of_charge / self.max_state_of_charge
            if self.max_state_of_charge != 0
            else 1
        )

    @property
    def energy_consumption(self):
        return self._energy_consumption

    @property
    def velocity(self):
        return self._velocity

    def move(self, route_segment: Edge):
        distance = route_segment.distance
        velocity = self._velocity
        time = distance / velocity

        if not self.has_enough_state_of_charge(distance):
            raise RuntimeError(
                f"{str(self.__class__.__name__)} {self._id} has been tried to move but has not enough state of charge."
            )

        yield self._env.timeout(time)

        self._update_positions(route_segment.destination.position)
        self._update_state_of_charge(distance)

    def start_driving(self):
        self.state = VehicleState.DRIVING

        logging.debug(
            "Driving started.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def stop_driving(self):
        self.state = VehicleState.PARKING
        self.set_current_task(None)
        logging.debug(
            "Driving stopped.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def park(self):
        # Lift reservation
        self._reserved_for_user = None

        # Make vehicle available for others again
        self.state = VehicleState.PARKING

        logging.debug(
            "Parked.", extra={"clazz": self.__class__.__name__, "oid": self._id}
        )

    def reserve(self, user):
        self.state = VehicleState.RESERVED

        self._reserved_for_user = user

        logging.debug(
            f"Reserved to {user.id}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def has_enough_state_of_charge(self, distance):
        """
        Check if vehicle has enough SoC left for trip
        :param distance: in meter
        :return:
        """
        # Bike does not need to check SoC
        if self._mode == VehicleMode.BIKE:
            return True

        if self.energy_consumption * distance / 1000 >= self._current_state_of_charge:
            return False
        return True

    def _update_state_of_charge(self, distance):
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
            f"Current state of charge {round(self.current_state_of_charge, 2)}/{self.max_state_of_charge} ({round(self.current_state_of_charge / self.max_state_of_charge * 100, 2)}%).",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def _update_positions(self, new_position: Position):
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
            f"Current position {self.position} in region {region_id}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def mount_driver(self, driver: DriverInterface):
        if self._driver is not None:
            raise Exception(
                f"Vehicle {self._id} has already a driver {self._driver.identify_driver()}. Unable to mount driver."
            )

        self._driver = driver
        self._driver_mounted.succeed()
        self._driver_mounted = self._env.event()

        self.state = VehicleState.DRIVING

        logging.debug(
            f"Driver: {driver.identify_driver()} mounted vehicle.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def unmount_driver(self):
        if self._driver is None:
            raise Exception("Vehicle has no driver to unmount.")

        tmp_driver_id = self._driver.identify_driver()
        self._driver = None
        self._driver_unmounted.succeed()
        self._driver_unmounted = self._env.event()

        self.state = VehicleState.PARKING

        logging.debug(
            f"Driver: {tmp_driver_id} unmounted vehicle.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def prepare_for_service_task(self, caller, task):
        self.state = VehicleState.PRE_SERVICE
        logging.debug(
            f"Marked for Service Task [{task}] by {caller}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def relocate(self, route_segment: Edge, time, relocator):
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
                f"Vehicle {self._id} has a driver. Revoke relocation task.",
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
            f"Vehicle relocated by {relocator} from {old_position} to {self.position} in {time} minutes.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def plug_to_charging_station(self):
        self.state = VehicleState.CHARGING

        self._charging_station_plugged_in.succeed()
        self._charging_station_plugged_in = self._env.event()

        logging.debug(
            "Vehicle plugged in to charging station.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def unplug_from_charging_station(self):
        self.state = VehicleState.PARKING

        self._charging_station_plugged_out.succeed()
        self._charging_station_plugged_out = self._env.event()

        logging.debug(
            "Vehicle plugged out from charging station.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def charge(self, charging_time, amount=0):
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
            f"Vehicle charged {amount} kWh and has now {self._current_state_of_charge} kWh out of {self._max_state_of_charge}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def __str__(self):
        return f"I have {self.available_seats} passengers on boards"
