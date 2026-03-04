from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, Any

from simulation.helper.vehicle_states import VehicleStates
from simulation.vehicle.mixins.reservable_mixin import ReservableMixin
from simulation.vehicle.movement_stats import MovementStats

from .vehicle import Vehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.infrastructure.network.edge import Edge
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.reservation import Reservation


class SharedVehicle(Vehicle, ReservableMixin):  # noqa: D101
    __slots__ = ("_price_per_minute", "_price_per_trip", "_reservation")

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        position: GeodesicPosition,
        vehicle_config: VehicleConfig,
    ) -> None:
        super().__init__(
            sim=sim, fleet=fleet, position=position, vehicle_config=vehicle_config
        )

        self._price_per_minute: float = vehicle_config.PRICE_PER_MIN
        self._price_per_trip: float = vehicle_config.PRICE_PER_TRIP

        self._reservation: Reservation | None = None
        self._is_in_use: bool = False

    @property
    def price_per_minute(self) -> float:  # noqa: D102
        return self._price_per_minute

    @property
    def price_per_trip(self) -> float:  # noqa: D102
        return self._price_per_trip

    def move(self, route_segment: Edge) -> Generator[Any, Any, MovementStats]:  # noqa: D102
        distance = route_segment.distance
        time = self.calculate_travel_time(distance)

        yield self._env.timeout(time)

        self._update_position(route_segment.destination.position)
        energy_consumed = self.energy_system.consume_for_distance(distance)
        return MovementStats(
            energy_consumed=energy_consumed,
            distance_travelled=distance,
            time_taken=time,
        )

    def wait_for_user(self) -> None:
        """Set vehicle to WAITING_FOR_USER state while user walks to pickup."""
        self._set_state(VehicleStates.WAITING_FOR_USER)
        self.logger.debug("Waiting for user.")

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
        # TODO: Do we still need this check ?
        if self._driver is not None or len(self._passengers) > 0:
            self.logger.error(
                "Vehicle %s has a driver. Revoke relocation task.", self.uid
            )

            raise Exception(
                f"Vehicle {self.uid} has a driver {self._driver}. Unable to relocate vehicle."
            )

        self._set_state(VehicleStates.RELOCATING)

        yield self._env.timeout(time)

        # Save old position for logging purposes
        old_position = self.position

        # Update new position of vehicle
        self._update_position(route_segment.destination.position)

        self._vehicle_relocation_finished.succeed()
        self._vehicle_relocation_finished = self._env.event()
        self._set_state(VehicleStates.STANDBY)

        self.logger.debug(
            "Vehicle relocated by %s from %s to %s in %s minutes.",
            relocator,
            old_position,
            self.position,
            time,
        )

    def plug_to_charging_station(self) -> None:  # noqa: D102
        self._set_state(VehicleStates.CHARGING)

        self.logger.debug("Vehicle plugged in to charging station.")

    def unplug_from_charging_station(self):  # noqa: ANN201, D102
        self._set_state(VehicleStates.STANDBY)

        self.logger.debug("Vehicle plugged out from charging station.")

    def charge(  # noqa: D102
        self, charging_time: float, amount: float = 0
    ) -> Generator[Any, Any, Any]:
        # TODO: This should be somewhere else. Either the base class or energy system or a dedicated component.

        energy_before = self.energy_system.current_energy_absolute

        # Delegate to energy system
        yield from self.energy_system.refill(amount, charging_time)

        charged = self.energy_system.current_energy_absolute - energy_before
        self.logger.debug(
            "Vehicle charged %s (units) and has now %s out of %s.",
            charged,
            self.energy_system.current_energy_absolute,
            self.energy_system.capacity,
        )

    def __str__(self):  # noqa: ANN204, D105
        return f"I am a shared vehicle with uid {self.uid} and state {self.state}."
