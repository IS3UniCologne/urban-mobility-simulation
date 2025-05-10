import logging

from simpy import Environment

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleMode
from simulation.helper.random.random_manager import RandomManager
from simulation.infrastructure.network.edge import Edge
from simulation.vehicle.interfaces.driver_interface import DriverInterface

from ..helper.configuration.configuration import Configuration
from ..operator.data_transfer_object.vehicle_allocation import VehicleAllocation
from .vehicle import Vehicle, VehicleState

# class RideHailingVehicleState(Enum):
#     INITIALIZED = 0
#     PARKING = 1
#     DRIVING = 2
#     RELOCATING = 3
#     CHARGING = 4
#     PRE_SERVICE = 5
#     SOME_STATE = 1002
#     RESERVED = 1001
#     MOVING_TO_PICK_UP_POS = 1003


class RideHailingVehicle(Vehicle):
    __slots__ = (
        "_is_electric",
        "_fleet",
        "travel_costs",
        "charging_costs",
        "_suggested",
        "_estimated_completion_time",
        "_destination",
        "_emergency_soc_buffer_percent",
        "_price_per_minute",
        "_available_seats",
        "_max_available_seats",
        "_seats",
        "_driver",
        "_velocity",
        "_current_state_of_charge",
        "_max_state_of_charge",
        "_energy_consumption",
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

    exposes = Vehicle.exposes + ["_fleet", "_current_state_of_charge", "_suggested"]

    def __init__(
        self,
        env: Environment,
        fleet,
        position,
        velocity,
        vehicle_mode: VehicleMode,
        max_available_seats=1,
        max_state_of_charge=1,
        energy_consumption=0.01,
        price_per_min=1,
        driver: DriverInterface = None,
        is_electric=True,
    ):
        super().__init__(
            env=env,
            fleet=fleet,
            position=position,
            velocity=velocity,
            max_available_seats=max_available_seats,
            vehicle_mode=vehicle_mode,
        )

        self._price_per_minute = price_per_min
        self._driver = None
        self._is_electric = is_electric
        self.travel_costs = 0
        self.charging_costs = 0

        self._config = Configuration()

        # State Of Charge
        self._max_state_of_charge = max_state_of_charge  # in kWh
        initial_state_of_charge_percentage = self._config.ride_hailing_vehicles[
            "RideHailingCar"
        ].INITIAL_SOC
        if initial_state_of_charge_percentage == 0:
            initial_state_of_charge_percentage = RandomManager().uniform(
                low=0.2, high=0.8, component="INITIALSOC"
            )

        self._current_state_of_charge = (
            max_state_of_charge * initial_state_of_charge_percentage
        )  # in kWh #
        self._energy_consumption = energy_consumption  # in kWh/km
        if not self._is_electric:
            self._energy_consumption = (
                energy_consumption
                * self._config.ride_hailing_vehicles[
                    "RideHailingCar"
                ].EV_RELATIVE_ENERGY_CONSUMPTION
            )

        #### Vehicle Events
        # Driving Events
        self._vehicle_parked = self._env.event()
        self._user_mounted = self._env.event()
        self._driving_started = self._env.event()
        self._driving_finished = self._env.event()
        self._user_unmounted = self._env.event()
        self._arrived_at_pick_up_position = self._env.event()

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
        self._suggested = False

        # Driver Interface
        if driver is not None:
            self.mount_driver(driver)

        # Estimation information for finishing the current task
        self._estimated_completion_time = 0
        self._destination = None

        # costs
        self._cost_km = self._config.ride_hailing_vehicles["RideHailingCar"].COST_PER_KM
        self._charging_cost_per_kWh = self._config.ride_hailing_vehicles[
            "RideHailingCar"
        ].CHARGING_COST_PER_KWH

        self._emergency_soc_buffer_percent: float

    @property
    def id(self):
        return self._id

    @property
    def price_per_minute(self):
        return self._price_per_minute

    @price_per_minute.setter
    def price_per_minute(self, price_per_minute):
        self._price_per_minute = price_per_minute

    @property
    def reserved_for_user(self):
        return self._reserved_for_user

    @property
    def max_state_of_charge(self):
        return self._max_state_of_charge

    @property
    def current_state_of_charge(self):
        return self._current_state_of_charge

    @property
    def current_relative_state_of_charge(self):
        return self.current_state_of_charge / self.max_state_of_charge

    @property
    def energy_consumption(self):
        return self._energy_consumption

    @property
    def estimated_completion_time(self):
        return self._estimated_completion_time

    @estimated_completion_time.setter
    def estimated_completion_time(self, estimated_completion_time):
        self._estimated_completion_time = estimated_completion_time

    @property
    def destination(self):
        return self._destination

    @property
    def is_electric(self):
        return self._is_electric

    @destination.setter
    def destination(self, destination):
        self._destination = destination

    def move(self, route_segment: Edge, relocating=False):
        distance = route_segment.distance
        velocity = self._velocity
        time = distance / velocity
        self.estimated_completion_time = self._env.now + time
        self.destination = route_segment.destination

        if not self.has_enough_state_of_charge(
            distance, consider_buffer=not relocating
        ):
            raise RuntimeError(
                f"{str(self.__class__.__name__)} {self._id} has been tried to move but has not enough state of charge."
            )

        yield self._env.timeout(time)
        try:
            self._update_positions(route_segment.destination)
        except Exception:
            self._update_positions(route_segment.destination.position)
        self._update_state_of_charge(distance)
        self.travel_costs += distance / 1000 * self._cost_km
        self.estimated_completion_time = 0

    def move_to_pick_up_position(self, vehicle_assignment: VehicleAllocation):
        # Wait for event
        yield vehicle_assignment.user._vehicle_allocated
        self._vehicle_assignment = vehicle_assignment
        # Set current state
        self.state = VehicleState.MOVING_TO_PICK_UP_POS

        ###
        vehicle_soc_before_driving = self.current_state_of_charge
        route_segment = (
            vehicle_assignment.associated_transportation_alternative.route_to_pickup
        )

        # Calculate route to pick up position, and update user's position
        yield self._env.process(self.move(route_segment))

        # State of Charge after driving
        vehicle_soc_after_driving = self.current_state_of_charge

        # Consumed Energy (kWh)
        user_energy_consumption = vehicle_soc_before_driving - vehicle_soc_after_driving

        vehicle_assignment.associated_transportation_alternative.set_energy_consumed(
            user_energy_consumption
        )

        # Trigger next event
        self._arrived_at_pick_up_position.succeed()
        logging.debug(
            f"Arrived at pick up position {self.position} at time {self._env.now}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )
        self._arrived_at_pick_up_position = self._env.event()

    def start_driving(self):
        self._suggested = False
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
        self._driving_finished.succeed()
        self._driving_finished = self._env.event()
        # self._suggested = False
        # Make vehicle available for others again
        self.state = VehicleState.PARKING

        logging.debug(
            "Parked.", extra={"clazz": self.__class__.__name__, "oid": self._id}
        )

    def reserve(self, user):
        previous_state = self.state
        self.state = VehicleState.RESERVED

        self._reserved_for_user = user

        logging.debug(
            f"Reserved to {user.id} and previous state was {previous_state}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def has_enough_state_of_charge(self, distance, consider_buffer=True):
        """
        Check if vehicle has enough SoC left for trip
        :param distance: in meter
        :param consider_buffer: if True (default), self._emergency_soc_buffer_percent is taken into account
        :return:
        """
        if (
            self.energy_consumption * distance / 1000
            >= self._current_state_of_charge
            - (
                self._emergency_soc_buffer_percent * self._max_state_of_charge
                if consider_buffer
                else 0
            )
        ):
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
            # TODO: this should not happen and throw something like a SimulationConstraintException
            raise Exception
            self._current_state_of_charge = 0.0

        logging.debug(
            f"Current state of charge {round(self.current_state_of_charge, 2)}/{self.max_state_of_charge} ({round(self.current_state_of_charge / self.max_state_of_charge * 100, 2)}%).",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def _update_positions(self, new_position: GeodesicPosition):
        # Update Vehicle Position
        old_position = self.position
        self.position = new_position

        # Update Position of Driver
        if self._driver:
            self._driver.position = new_position

        # Update Position of Passengers
        for passenger in self._seats:
            passenger.position = new_position

        region_id = self.position.get_region_id()

        logging.debug(
            f"Old position {old_position} > Current position {self.position} in region {region_id}.",
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

    def relocate(self, route_segment: Edge):
        """
        Relocate vehicle independent of state of charge and availability of driver
        :param route_segment:
        :param time:
        :param relocator: The exact entity (e.g., Service Worker ID) that relocated the vehicle
        :return:
        """
        if self._driver is not None or len(self._seats) > 0:
            logging.debug(
                f"Vehicle {self._id} has a driver {self._driver.identify_driver()}. Revoke relocation task.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )

            yield self._env.timeout(1)

            return

            raise Exception(
                f"Vehicle {self._id} has a driver {self._driver.identify_driver()}. Unable to relocate vehicle."
            )

        # Invoke event to notify listeners that relocation started
        self._vehicle_relocation_started.succeed()
        self._vehicle_relocation_started = self._env.event()
        self.state = VehicleState.RELOCATING

        yield self._env.process(self.move(route_segment=route_segment, relocating=True))

        # Invoke event to notify listeners that relocation ended
        self._vehicle_relocation_finished.succeed()
        self._vehicle_relocation_finished = self._env.event()

        self.park()

    def waiting_for_charging(self):
        self.state = VehicleState.PRE_SERVICE

        logging.debug(
            "Vehicle started waiting in the queue.",
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
        self.state = VehicleState.CHARGING
        self._charging_station_charging_started.succeed()
        self._charging_station_charging_started = self._env.event()

        if amount == 0:
            amount = self._max_state_of_charge - self._current_state_of_charge

        # Update Current State of Charge
        self._current_state_of_charge += amount
        self.charging_costs += amount * self._charging_cost_per_kWh

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
        return f"ID: {self._id}, Position: {self.position}, State: {self.state}"
