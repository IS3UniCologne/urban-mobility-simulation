from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from simulation.helper.enums import AutonomyType, PropulsionType
from simulation.helper.vehicle_states import VehicleStates
from simulation.vehicle.mixins.reservable_mixin import ReservableMixin

from .vehicle import Vehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.infrastructure.route import Route
    from simulation.operator.cost_accounting import VehicleCostReporter
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.reservation import Reservation

    from ..operator.data_transfer_object.vehicle_allocation import VehicleAllocation


class RideHailingVehicle(Vehicle, ReservableMixin):  # noqa: D101
    __slots__ = (
        "_arrived_at_pick_up_position",
        "_charging_cost_per_kWh",
        "_charging_cost_per_kWh",
        "_charging_station_plugged_out",
        "_driver_availability_vector",
        "_is_electric",
        "_price_per_minute",
        "_reservation",
        "_vehicle_assignment",
    )

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        position: GeodesicPosition,
        vehicle_config: VehicleConfig,
        driver_availability_vector: list[int],
        cost_reporter: VehicleCostReporter,
    ) -> None:
        super().__init__(
            sim=sim,
            fleet=fleet,
            position=position,
            vehicle_config=vehicle_config,
            cost_reporter=cost_reporter,
        )

        self._price_per_minute = vehicle_config.PRICE_PER_MIN
        # TODO Change this to use type directly
        self._is_electric = (
            vehicle_config.PROPULSION_TYPE == PropulsionType.BATTERY_ELECTRIC
        )

        self._driver_availability_vector = driver_availability_vector

        # Vehicle Events
        self._arrived_at_pick_up_position: Event = self._env.event()
        self._charging_station_plugged_out: Event = self._env.event()

        self._reservation: Reservation | None = None
        self._is_in_use: bool = False

        if vehicle_config.AUTONOMY_TYPE == AutonomyType.HUMAN_DRIVEN:
            self._price_per_minute = vehicle_config.PRICE_PER_MIN
            self._set_state(VehicleStates.OFFLINE)
            self._env.process(self.run_shift_check_process())

    @property
    def price_per_minute(self) -> float:  # noqa: D102
        return self._price_per_minute

    @property
    def is_electric(self) -> bool:  # noqa: D102
        return self._is_electric

    def traverse_route(self, route: Route) -> Generator[Event, None, float]:
        """
        Traverse a route and update the expectations.

            This high-level function keeps track of the vehicle's estimated completion time and expected destination.

        Parameters
        ----------
        route : Route
            The route to traverse.

        Returns
        -------
        float
            Total energy consumed during traversal.
        """
        self.fleet.insert_into_en_route_spatial_index(self)

        # delegate to low level traversal of route segments
        total_energy = yield from super().traverse_route(route)

        self.fleet.delete_from_en_route_spatial_index(self)

        return total_energy

    def move_to_pick_up_position(  # noqa: D102
        self, vehicle_assignment: VehicleAllocation
    ) -> Generator[Event, None, None]:
        self._vehicle_assignment = vehicle_assignment

        if vehicle_assignment.transportation_alternative.route_to_pickup is None:
            self.logger.error(
                "Vehicle assignment %s has no route to pickup. Unable to move to pickup position.",
                vehicle_assignment,
            )
            raise Exception(
                f"Vehicle assignment {vehicle_assignment} has no route to pickup. Unable to move to pickup position."
            )
        route = vehicle_assignment.transportation_alternative.route_to_pickup

        self._set_state(VehicleStates.PICK_UP)

        energy_consumed = yield from self.traverse_route(route)

        vehicle_assignment.increase_energy_consumed(energy_consumed)

        self._arrived_at_pick_up_position.succeed()

        self.logger.debug(
            "Arrived at pick up position %s to pick up user %s.",
            self.position,
            vehicle_assignment.user.uid,
        )

    def start_driving(self) -> None:  # noqa: D102
        self._set_state(VehicleStates.DRIVING)

        # Reset pickup arrival event for next trip
        self._arrived_at_pick_up_position = self._env.event()

        self.logger.debug("Driving started.")

    def relocate(self, route: Route) -> Generator[Any, Any, Any]:
        """Relocate vehicle.

        Parameters
        ----------
        route : Route
            The route to relocate the vehicle along.
        """
        if self._driver is not None or len(self._passengers) > 0:
            self.logger.debug(
                "Vehicle %s has a driver %s. Revoke relocation task.",
                self.uid,
                self._driver,
            )

            raise Exception(
                f"Vehicle {self.uid} has a driver {self._driver}. Unable to relocate vehicle."
            )

        self._set_state(VehicleStates.RELOCATING)

        yield from self.traverse_route(route)

        # Invoke event to notify listeners that relocation ended
        self._vehicle_relocation_finished.succeed()
        self._vehicle_relocation_finished = self._env.event()

        self._set_state(VehicleStates.STANDBY)

    def wait_for_charging(self) -> None:  # noqa: D102
        self._set_state(VehicleStates.WAITING_FOR_CHARGING)

        self.logger.debug("Vehicle started waiting in the queue.")

    def plug_to_charging_station(self) -> None:  # noqa: D102
        self._set_state(VehicleStates.CHARGING)
        self.logger.debug("Vehicle plugged in to charging station.")

    def unplug_from_charging_station(self) -> None:  # noqa: D102
        self._set_state(VehicleStates.STANDBY)

        self._charging_station_plugged_out.succeed()
        self._charging_station_plugged_out = self._env.event()

        self.logger.debug("Vehicle plugged out from charging station.")

    def abort_charging_wait(self) -> None:
        """Cancel waiting for charging and return to standby."""
        self._set_state(VehicleStates.STANDBY)

    # TODO: Should this be part of the EnergySystem ?
    def charge(  # noqa: D102
        self, charging_time: float, cost_per_kWh: float, charge_amount: float = 0
    ) -> Generator[Event, None, None]:
        self._set_state(VehicleStates.CHARGING)

        if charge_amount == 0:
            charge_amount = (
                self.energy_system.capacity - self.energy_system.current_energy_absolute
            )

        self.charging_costs += charge_amount * cost_per_kWh
        energy_before = self.energy_system.current_energy_absolute

        # Charge
        yield from self.energy_system.refill(charge_amount, charging_time)

        self._cost_reporter.record_energy_charged(
            self, self.energy_system.current_energy_absolute - energy_before
        )

        self.logger.debug(
            "Vehicle charged %s kWh and has now %s kWh out of %s.",
            charge_amount,
            self.energy_system.current_energy_absolute,
            self.energy_system.capacity,
        )

    # TODO: This whole logic should be decided by the operations, not the vehicle.
    def decide_to_get_online(self) -> bool:  # noqa: D102
        go_online = False
        fleet_size_threshold = self._driver_availability_vector
        time = self._env.now
        hour = int(
            (time % 1440) / 60
        )  # TODO: This rounds to the nearest hour, should we use SimulationTimeConverter.hour_of_day instead?
        number_of_online_vehicles = len(
            self.fleet.vehicles_by_autonomy[AutonomyType.HUMAN_DRIVEN]
        ) - len(
            self.fleet.vehicles_by_state.get(VehicleStates.OFFLINE, set()).intersection(
                self.fleet.vehicles_by_autonomy[AutonomyType.HUMAN_DRIVEN]
            )
        )
        if number_of_online_vehicles <= fleet_size_threshold[hour]:
            go_online = True
        return go_online

    def decide_to_get_offline(self) -> bool:  # noqa: D102
        go_offline = False
        fleet_size_threshold = self._driver_availability_vector
        time = self._env.now
        hour = int(
            (time % 1440) / 60
        )  # TODO: This rounds to the nearest hour, should we use SimulationTimeConverter.hour_of_day instead?
        number_of_online_vehicles = len(
            self.fleet.vehicles_by_autonomy[AutonomyType.HUMAN_DRIVEN]
        ) - len(
            self.fleet.vehicles_by_state.get(VehicleStates.OFFLINE, set()).intersection(
                self.fleet.vehicles_by_autonomy[AutonomyType.HUMAN_DRIVEN]
            )
        )
        if fleet_size_threshold is None:
            return False
        if hour >= len(fleet_size_threshold):
            hour = len(fleet_size_threshold) - 1
        if hour < 0:
            hour = 0
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
            if self.state is VehicleStates.OFFLINE:
                go_online = self.decide_to_get_online()
                if go_online:
                    self._go_online()
            # If the driver is online we check the decision of getting offline
            elif self.state is VehicleStates.STANDBY:
                go_offline = self.decide_to_get_offline()
                if go_offline:
                    if (
                        self.state is VehicleStates.STANDBY
                    ):  # TODO: Why are we checking for parking twice in a row?
                        self._go_offline()
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
                        self._go_offline()
            # we check driver decisions every one hour
            yield self._env.timeout(15)
