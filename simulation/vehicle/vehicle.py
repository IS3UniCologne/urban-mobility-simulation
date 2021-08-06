from abc import ABC, abstractmethod
from enum import Enum

from simpy import Environment

from simulation.agent.agent import Agent
from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge
from simulation.vehicle.interfaces.driver_interface import DriverInterface

import logging

from simulation.vehicle.interfaces.passenger_interface import PassengerInterface


class VehicleState(Enum):
    INITIALIZED = 0
    PARKING = 1
    DRIVING = 2
    RELOCATING = 3
    CHARGING  = 4
    PRE_SERVICE = 5 # Marked for Service Tasks

class Vehicle(ABC):
    vehicle_id = 0

    def __init__(self, env: Environment, position, available_seats, max_available_seats, max_state_of_charge, energy_consumption, velocity, driver: DriverInterface):
        self(env, position, available_seats, max_available_seats, max_state_of_charge, energy_consumption, velocity)
        self.mount_driver(driver)

    def __init__(self, env: Environment, position, available_seats, max_available_seats, max_state_of_charge, energy_consumption, velocity):
        self._id = Vehicle.vehicle_id
        Vehicle.vehicle_id += 1  # Increment User Id
        self._env = env
        self._position = position
        self._available_seats = available_seats
        self._max_available_seats = max_available_seats
        self._seats = []
        self._driver = None
        self._velocity = velocity   # meter per minute (16.67m/min = 1kmh)

        # State Of Charge
        self._max_state_of_charge = max_state_of_charge # in kWh
        self._current_state_of_charge = max_state_of_charge # in kWh
        self._energy_consumption = energy_consumption # in kWh/km

        #### Vehicle Events
        # Driving Events
        self._vehicle_parked = self._env.event()
        self._user_mounted = self._env.event()
        self._driving_started = self._env.event()
        self._driving_finished = self._env.event()
        self._user_demounted = self._env.event()

        self._driver_mounted = self._env.event()
        self._driver_unmounted = self._env.event()


        # Relocation Events
        self._vehicle_relocation_started = self._env.event()
        self._vehicle_relocation_finished = self._env.event()

        # Spatial Events
        self._position_changed = self._env.event()

        # Charging Events
        self._charging_station_plugged_in = self._env.event()
        self._charging_station_charging_started = self._env.event()
        self._charging_station_charging_finished = self._env.event()
        self._charging_station_plugged_out = self._env.event()

        # Initial State
        self.state = VehicleState.PARKING


    # Properties
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

    @property
    def available_seats(self):
        return self._available_seats

    @available_seats.setter
    def available_seats(self, available_seats):
        self._available_seats = available_seats

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
        return self.current_state_of_charge/self.max_state_of_charge

    @property
    def energy_consumption(self):
        return self._energy_consumption

    @property
    def velocity(self):
        return self._velocity

    # Methods
    @abstractmethod
    def start_driving(self):
        pass

    @abstractmethod
    def stop_driving(self):
        pass

    @abstractmethod
    def park(self):
        pass

    def move(self, route_segment: Edge):
        distance = route_segment.distance
        velocity = self._velocity
        time = distance / velocity

        if not self.has_enough_state_of_charge(distance):
            raise RuntimeError(f"{str(self.__class__.__name__)} {self._id} has been tried to move but has not enough state of charge.")

        yield self._env.timeout(time)

        self._update_positions(route_segment.destination.position)
        self._update_state_of_charge(distance)

    def has_enough_state_of_charge(self, distance):
        """
        Check if vehicle has enough SoC left for trip
        :param distance: in meter
        :return:
        """
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

        logging.debug(f'Current state of charge {round(self.current_state_of_charge, 2)}/{self.max_state_of_charge} ({round(self.current_state_of_charge/self.max_state_of_charge*100, 2)}%).',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})


    def _update_positions(self, new_position: Position):
        # Update Vehicle Position
        self.position = new_position

        # Update Position of Driver
        if self._driver:
            self._driver.position = new_position

        # Update Position of Passengers
        for passenger in self._seats:
            passenger.position = new_position

        region_id, _ = self._position.get_hexagon()

        logging.debug(f'Current position {self._position} in region {region_id}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})


    def mount_driver(self, driver: DriverInterface):
        if self._driver is not None:
            raise Exception(f'Vehicle {self._id} has already a driver {self._driver.identify_driver()}. Unable to mount driver.')

        self._driver = driver
        self._driver_mounted.succeed()
        self._driver_mounted = self._env.event()

        self.state == VehicleState.DRIVING

        logging.debug(f'Driver: {driver.identify_driver()} mounted vehicle.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def unmount_driver(self):
        if(self._driver is None):
            raise Exception('Vehicle has no driver to unmount.')

        tmp_driver_id=self._driver.identify_driver()
        self._driver = None
        self._driver_unmounted.succeed()
        self._driver_unmounted = self._env.event()

        self.state == VehicleState.PARKING

        logging.debug(f'Driver: {tmp_driver_id} unmounted vehicle.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def mount_passenger(self, passenger: PassengerInterface):
        if(len(self._seats) < self._available_seats):
            self._seats.append(passenger)
            self._available_seats -= 1

            self._user_mounted.succeed()
            self._user_mounted = self._env.event()

            logging.debug(f'Passenger: {passenger.identify_passenger()} mounted vehicle.',
                          extra={"clazz": self.__class__.__name__, "oid": self._id})

        elif passenger in self._seats:
            raise Exception('Passenger is already in vehicle.')
        else:
            raise Exception('Vehicle is full.')

    def prepare_for_service_task(self, caller):
        self._state == VehicleState.PRE_SERVICE
        logging.debug(f'Marked for Service Task by {caller}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def unmount_passenger(self, passenger: PassengerInterface):
        if passenger in self._seats:
            self._seats.remove(passenger)
            self._available_seats += 1

            self._user_unmounted.succeed()
            self._user_unmounted = self._env.event()

            logging.debug(f'Passenger: {passenger.identify_passenger()} unmounted vehicle.',
                          extra={"clazz": self.__class__.__name__, "oid": self._id})
        else:
            raise Exception('Agent is not in vehicle.')

    def relocate(self, route_segment: Edge, time, relocator):
        """
        Relocate vehicle independent of state of charge and availability of driver
        :param route_segment:
        :param time:
        :param relocator: The exact entity (e.g., Service Worker ID) that relocated the vehicle
        :return:
        """
        if self._driver is not None:
            raise Exception(f'Vehicle {self._id} has a driver {self._driver.identify_driver()}. Unable to relocate vehicle.')
        elif len(self._seats) > 0:
            raise Exception(f'Vehicle {self._id} has a driver {self._driver.identify_driver()}. Unable to relocate vehicle.')

        # Invoke event to notify listeners that relocation started
        self._vehicle_relocation_started.succeed()
        self._vehicle_relocation_started = self._env.event()

        self._state = VehicleState.RELOCATING

        yield self._env.timeout(time)

        # Save old position for logging purposes
        old_position = self._position

        # Update new position of vehicle
        self._update_positions(route_segment.destination.position)

        # Invoke event to notify listeners that relocation ended
        self._vehicle_relocation_finished.succeed()
        self._vehicle_relocation_finished = self._env.event()

        self._state = VehicleState.PARKING

        logging.debug(f'Vehicle relocated by {relocator} from {old_position} to {self._position} in {time} minutes.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def plug_to_charging_station(self):
        self._state = VehicleState.CHARGING

        self._charging_station_plugged_in.succeed()
        self._charging_station_plugged_in = self._env.event()

        logging.debug(f'Vehicle plugged in to charging station.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def unplug_from_charging_station(self):
        self._state = VehicleState.PARKING

        self._charging_station_plugged_out.succeed()
        self._charging_station_plugged_out = self._env.event()

        logging.debug(f'Vehicle plugged out from charging station.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def charge(self, charging_time, amount = 0):
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

        logging.debug(f'Vehicle charged {amount} kWh and has now {self._current_state_of_charge} kWh out of {self._max_state_of_charge}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})


    @abstractmethod
    def __str__(self):
        pass
