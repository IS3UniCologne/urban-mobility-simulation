from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from simulation.helper.configuration.enums import (
    AutonomyType,
    PropulsionType,
    VehicleState,
)

from .vehicle import Vehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.environment.position import Position
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.infrastructure.network.edge import Edge
    from simulation.operator.operations_management.service_tasks.service_task import (
        ServiceTask,
    )
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.interfaces.driver_interface import DriverInterface

    from ..operator.data_transfer_object.vehicle_allocation import VehicleAllocation


class RideHailingVehicle(Vehicle):  # noqa: D101
    __slots__ = (
        "_arrived_at_pick_up_position",
        "_available_seats",
        "_charging_cost_per_kWh",
        "_charging_station_charging_finished",
        "_charging_station_charging_started",
        "_charging_station_plugged_in",
        "_charging_station_plugged_out",
        "_cost_km",
        "_cost_km_seats",
        "_current_state_of_charge",
        "_destination",
        "_driver",
        "_driver_availability_vector",
        "_driver_mounted",
        "_driver_unmounted",
        "_driving_finished",
        "_driving_started",
        "_emergency_soc_buffer_percent",
        "_emergency_soc_buffer_percent",
        "_energy_consumption",
        "_env",
        "_estimated_completion_time",
        "_is_electric",
        "_max_available_seats",
        "_max_state_of_charge",
        "_offline_duration",
        "_offline_event",
        "_online_event",
        "_price_per_minute",
        "_reserved_for_user",
        "_shift_duration",
        "_shift_earn",
        "_shift_end_time",
        "_shift_start_time",
        "_suggested",
        "_total_earn",
        "_user_mounted",
        "_user_unmounted",
        "_vehicle_assignment",
        "_vehicle_parked",
        "_vehicle_relocation_finished",
        "_vehicle_relocation_started",
        "_velocity",
        "charging_costs",
        "travel_costs",
    )

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        position: Position,
        vehicle_config: VehicleConfig,
        driver_availability_vector: list[int] | None,
    ) -> None:
        super().__init__(
            sim=sim, fleet=fleet, position=position, vehicle_config=vehicle_config
        )

        self._env = sim.env
        self._price_per_minute = vehicle_config.PRICE_PER_MIN
        self._driver: DriverInterface | None = None
        # TODO Change this to use type directly
        self._is_electric = (
            vehicle_config.PROPULSION_TYPE == PropulsionType.BATTERY_ELECTRIC
        )

        self._driver_availability_vector = driver_availability_vector
        self.travel_costs = 0
        self.charging_costs = 0

        # State Of Charge
        self._max_state_of_charge = vehicle_config.MAX_STATE_OF_CHARGE  # in kWh

        # TODO: move this to Vehicle or Fleet Factory class
        initial_state_of_charge_percentage = vehicle_config.INITIAL_SOC
        if initial_state_of_charge_percentage == 0:
            initial_state_of_charge_percentage = self._sim.random_manager.uniform(
                low=0.2, high=0.8, component="INITIALSOC"
            )
        self._current_state_of_charge = (
            self._max_state_of_charge * initial_state_of_charge_percentage
        )  # in kWh #
        self._energy_consumption = vehicle_config.ENERGY_CONSUMPTION  # in kWh/km

        # TODO: What are we even doing here?
        if not self._is_electric:
            self._energy_consumption = (
                vehicle_config.ENERGY_CONSUMPTION
                * vehicle_config.EV_RELATIVE_ENERGY_CONSUMPTION
            )

        #### Vehicle Events
        # Driving Events
        self._vehicle_parked: Event = self._env.event()
        self._user_mounted: Event = self._env.event()
        self._driving_started: Event = self._env.event()
        self._driving_finished: Event = self._env.event()
        self._user_unmounted: Event = self._env.event()
        self._arrived_at_pick_up_position: Event = self._env.event()

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
        self._reserved_for_user = None
        self._suggested = False

        # Estimation information for finishing the current task
        self._estimated_completion_time: int = 0
        self._destination: Position = None

        # costs
        self._cost_km: float = vehicle_config.COST_PER_KM
        self._charging_cost_per_kWh: float = vehicle_config.CHARGING_COST_PER_KWH

        self._emergency_soc_buffer_percent: float = vehicle_config.EMERGENCY_SOC_BUFFER

        if vehicle_config.AUTONOMY_TYPE == AutonomyType.HUMAN_DRIVEN:
            self._price_per_minute = vehicle_config.PRICE_PER_MIN
            self._total_earn = 0
            self._shift_earn = 0
            self._shift_duration = 0
            self._offline_duration = 0
            self._shift_start_time = None
            self._shift_end_time = 0
            self.state = VehicleState.OFFLINE
            self._online_event = self._env.event()
            self._offline_event = self._env.event()

            self._emergency_soc_buffer_percent = vehicle_config.EMERGENCY_SOC_BUFFER

            self._env.process(self.run_shift_check_process())

    @property
    def price_per_minute(self) -> float:  # noqa: D102
        return self._price_per_minute

    @price_per_minute.setter
    def price_per_minute(self, price_per_minute: float) -> None:
        self._price_per_minute = price_per_minute

    @property
    def reserved_for_user(self) -> User:  # noqa: D102
        return self._reserved_for_user

    @property
    def max_state_of_charge(self) -> float:  # noqa: D102
        return self._max_state_of_charge

    @property
    def current_state_of_charge(self) -> float:  # noqa: D102
        return self._current_state_of_charge

    @property
    def current_relative_state_of_charge(self) -> float:  # noqa: D102
        return self.current_state_of_charge / self.max_state_of_charge

    @property
    def energy_consumption(self) -> float:  # noqa: D102
        return self._energy_consumption

    @property
    def estimated_completion_time(self) -> float:  # noqa: D102
        return self._estimated_completion_time

    @estimated_completion_time.setter
    def estimated_completion_time(self, estimated_completion_time: float) -> None:
        self._estimated_completion_time = estimated_completion_time

    @property
    def destination(self) -> Position:  # noqa: D102
        return self._destination

    @property
    def is_electric(self) -> bool:  # noqa: D102
        return self._is_electric

    @destination.setter
    def destination(self, destination: Position) -> None:
        self._destination = destination

    def move(  # noqa: D102
        self, route_segment: Edge, relocating: bool = False
    ) -> Generator[Event, None, None]:
        distance = route_segment.distance
        velocity = self._velocity
        time = distance / velocity
        self.estimated_completion_time = self._env.now + time
        self.destination = route_segment.destination

        if not self.has_enough_state_of_charge(
            distance, consider_buffer=not relocating
        ):
            raise RuntimeError(
                f"{self.__class__.__name__!s} {self.uid} has been tried to move but has not enough state of charge."
            )

        yield self._env.timeout(time)
        try:
            self._update_positions(route_segment.destination)
        except Exception:
            self._update_positions(route_segment.destination.position)
        self._update_state_of_charge(distance)
        self.travel_costs += distance / 1000 * self._cost_km
        self.estimated_completion_time = 0

    def move_to_pick_up_position(  # noqa: D102
        self, vehicle_assignment: VehicleAllocation
    ) -> Generator[Event, None, None]:
        # Wait for event
        yield vehicle_assignment.user._vehicle_allocated  # noqa: SLF001
        self._vehicle_assignment = vehicle_assignment
        # Set current state
        self.state = VehicleState.MOVING_TO_PICK_UP_POS

        ###
        vehicle_soc_before_driving = self.current_state_of_charge
        route_segment = (
            vehicle_assignment.associated_transportation_alternative.route_to_pickup
        )

        # User waiting time (after arrival)
        start_waiting = self._env.now

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
        self.logger.debug(
            "Arrived at pick up position %s after %s time units to pick up user %s.",
            self.position,
            self._env.now - start_waiting,
            self._reserved_for_user,
        )
        self._arrived_at_pick_up_position = self._env.event()

    def start_driving(self) -> None:  # noqa: D102
        self._suggested = False
        self.state = VehicleState.DRIVING

        self.logger.debug("Driving started.")

    def stop_driving(self) -> None:  # noqa: D102
        self.state = VehicleState.PARKING
        self.set_current_task(None)

        self.logger.debug("Driving stopped.")

    def park(self) -> None:  # noqa: D102
        # Lift reservation
        self._reserved_for_user = None
        self._driving_finished.succeed()
        self._driving_finished = self._env.event()
        # self._suggested = False
        # Make vehicle available for others again
        self.state = VehicleState.PARKING

        self.logger.debug("Parked.")

    def reserve(self, user: User) -> None:  # noqa: D102
        previous_state = self.state
        self.state = VehicleState.RESERVED

        self._reserved_for_user = user

        self.logger.debug(
            "Reserved to %s and previous state was %s.", user.uid, previous_state
        )

    def has_enough_state_of_charge(
        self, distance: float, consider_buffer: bool = True
    ) -> bool:
        """
        Check if vehicle has enough SoC left for trip
        :param distance: in meter
        :param consider_buffer: if True (default), self._emergency_soc_buffer_percent is taken into account
        :return:
        """  # noqa: D205, D400
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

    def _update_state_of_charge(self, distance: float) -> None:
        """
        Update state of charge of vehicles based on driven distance.
        SoC = SoC_old - EnergyConsumption (kWh/km) * km
        :param distance: Distance driven
        """  # noqa: D205, D400
        energy_consumed = self.energy_consumption * distance / 1000
        self._current_state_of_charge -= energy_consumed

        if self._current_state_of_charge < 0:
            # TODO: this should not happen and throw something like a SimulationConstraintException
            raise Exception
            self._current_state_of_charge = 0.0

        self.logger.debug(
            "Current state of charge %s/%s (%s%%).",
            round(self.current_state_of_charge, 2),
            self.max_state_of_charge,
            round(self.current_state_of_charge / self.max_state_of_charge * 100, 2),
        )

    def _update_positions(self, new_position: GeodesicPosition) -> None:
        # Update Vehicle Position
        self.position = new_position

        # Update Position of Driver
        if self._driver:
            self._driver.position = new_position

        # Update Position of Passengers
        for passenger in self._passengers:
            passenger.position = new_position

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

    def relocate(self, route_segment: Edge) -> Generator[Any, Any, Any]:
        """
        Relocate vehicle independent of state of charge and availability of driver
        :param route_segment:
        :param time:
        :param relocator: The exact entity (e.g., Service Worker ID) that relocated the vehicle
        :return:
        """  # noqa: D205, D400
        if self._driver is not None or len(self._passengers) > 0:
            self.logger.debug(
                "Vehicle %s has a driver %s. Revoke relocation task.",
                self.uid,
                self._driver.identify_driver(),
            )

            yield self._env.timeout(1)

            return

            raise Exception(
                f"Vehicle {self.uid} has a driver {self._driver.identify_driver()}. Unable to relocate vehicle."
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

    def waiting_for_charging(self) -> None:  # noqa: D102
        self.state = VehicleState.PRE_SERVICE

        self.logger.debug("Vehicle started waiting in the queue.")

    def plug_to_charging_station(self) -> None:  # noqa: D102
        self.state = VehicleState.CHARGING

        self._charging_station_plugged_in.succeed()
        self._charging_station_plugged_in = self._env.event()

        self.logger.debug("Vehicle plugged in to charging station.")

    def unplug_from_charging_station(self) -> None:  # noqa: D102
        self.state = VehicleState.PARKING

        self._charging_station_plugged_out.succeed()
        self._charging_station_plugged_out = self._env.event()

        self.logger.debug("Vehicle plugged out from charging station.")

    def charge(  # noqa: D102
        self, charging_time: float, amount: float = 0
    ) -> Generator[Event, None, None]:
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

        self.logger.debug(
            "Vehicle charged %s kWh and has now %s kWh out of %s.",
            amount,
            self._current_state_of_charge,
            self._max_state_of_charge,
        )

    ### stuff from RideHailingCar ###

    @property
    def total_earn(self) -> float:  # noqa: D102
        return self._total_earn

    @property
    def shift_earn(self) -> float:  # noqa: D102
        return self._shift_earn

    @property
    def shift_duration(self) -> float:  # noqa: D102
        return self._shift_duration

    @property
    def offline_duration(self) -> float:  # noqa: D102
        return self._offline_duration

    @property
    def shift_start_time(self) -> float:  # noqa: D102
        return self._shift_start_time

    @property
    def shift_end_time(self) -> float:  # noqa: D102
        return self._shift_end_time

    def update_shift_start_time(self) -> None:  # noqa: D102
        time = self._env.now
        self._shift_start_time = time

        self.logger.debug("Shift has started.")

    def update_shift_end_time(self) -> None:  # noqa: D102
        time = self._env.now
        self._shift_end_time = time

        self.logger.debug("Shift has ended.")

    def update_shift_duration(self) -> None:  # noqa: D102
        self._shift_duration = self._env.now - self._shift_start_time

    def update_offline_duration(self) -> None:  # noqa: D102
        self._offline_duration = self._env.now - self._shift_end_time

    def update_idle_time(self):  # TODO  # noqa: ANN201, D102
        pass

    def get_online(self) -> None:  # noqa: D102
        self.state = VehicleState.PARKING
        self.update_shift_start_time()
        self._online_event.succeed()
        self._online_event = self._env.event()
        self.logger.debug("Driver gets online.")

    def get_offline(self) -> None:  # noqa: D102
        self.state = VehicleState.OFFLINE
        self._shift_earn = 0
        self.update_shift_end_time()
        self._offline_event.succeed()
        self._offline_event = self._env.event()
        self.logger.debug("Driver gets offline.")

    # TODO: This whole logic should be decided by the operations, not the vehicle.
    def decide_to_get_online(self) -> bool:  # noqa: D102
        go_online = False
        ### comment off when we have mode chioce variables
        # self.update_offline_duration()
        # time = self._env.now
        # week_day = int((time % (24 * 60 * 7)) / (24 * 60))
        # hour = int((time / 60) % 60)
        # offline_duration = self.offline_duration
        # shift_earned = self.shift_earn
        # driver_on_off_model.predict([[0, week_day, hour, offline_duration, shift_earned]])
        # if driver_on_off_model == 1:  # TODO: calibrate the parameters
        #     go_online = True
        fleet_size_threshold = self._driver_availability_vector
        time = self._env.now
        hour = int(
            (time % 1440) / 60
        )  # TODO: This rounds to the nearest hour, should we use SimulationTimeConverter.hour_of_day instead?
        number_of_online_vehicles = len(
            self.fleet.vehicles_by_state[VehicleState.ONLINE]
        )
        if number_of_online_vehicles <= fleet_size_threshold[hour]:
            go_online = True
        return go_online

    def decide_to_get_offline(self) -> bool:  # noqa: D102
        go_offline = False
        ### comment off when we have mode chioce variables
        # self.update_shift_duration()
        # time = self._env.now
        # week_day = int((time % (24 * 60 * 7)) / (24 * 60))
        # hour = int((time / 60) % 60)
        # shift_duration = self.shift_duration
        # shift_earned = self.shift_earn
        # driver_on_off_model.predict([[0, week_day, hour, shift_duration, shift_earned]])
        # if driver_on_off_model == 1:  # TODO: calibrate the parameters
        #     go_offline = True
        fleet_size_threshold = self._driver_availability_vector
        time = self._env.now
        hour = int(
            (time % 1440) / 60
        )  # TODO: This rounds to the nearest hour, should we use SimulationTimeConverter.hour_of_day instead?
        number_of_online_vehicles = len(
            self.fleet.vehicles_by_state[VehicleState.ONLINE]
        )
        if number_of_online_vehicles >= fleet_size_threshold[hour]:
            go_offline = True

        return go_offline

    def run_shift_check_process(self) -> Generator[Event, None, None]:
        """
        Run availability decision-making process of drivers
        :return:
        """  # noqa: D205, D400
        while True:
            # If the driver is offline we check the decision of getting online
            if self.state == VehicleState.OFFLINE:
                go_online = self.decide_to_get_online()
                if go_online:
                    self.get_online()
            # If the driver is online we check the decision of getting offline
            elif self.state in [VehicleState.PARKING]:
                self.update_offline_duration()
                go_offline = self.decide_to_get_offline()
                if go_offline:
                    if (
                        self.state == VehicleState.PARKING
                    ):  # TODO: Why are we checking for parking twice in a row?
                        self.get_offline()
                    # if the driver has a task to do we yield until its completion
                    else:
                        self.logger.debug(
                            "Driver is %s and has a task to do before getting offline.",
                            self.state,
                        )
                        yield (
                            self._driver_unmounted
                            | self._vehicle_relocation_finished
                            | self._charging_station_plugged_out
                        )
                        self.get_offline()
            # we check driver decisions every one hour
            yield self._env.timeout(15)
