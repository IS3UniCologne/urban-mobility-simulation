"""Service job for batch charging shared vehicles at a fleet base."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.operations_management.service_jobs.service_job import (
    ServiceJob,
)
from simulation.tasks.base.vehicle_session import VehicleSession
from simulation.tasks.operations.fleet_base_charging_task import FleetBaseChargingTask
from simulation.tasks.operations.service_worker_relocation_task import (
    ServiceWorkerRelocationTask,
)
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.enums import VehicleType
    from simulation.helper.types import RegionId
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.reservation import Reservation
    from simulation.vehicle.vehicle import Vehicle


class FleetBaseChargingJob(ServiceJob):
    """Batch charging of shared vehicles at a centralized fleet base.

    Selects vehicles below energy threshold, relocates them via service worker,
    and charges them at the fleet base.
    """

    __slots__ = (
        "_config",
        "_destination",
        "_distance_to_fleet_base",
        "_number_of_vehicles_to_charge",
        "_origin",
        "_state_of_charge_threshold",
        "_vehicle_fleet",
        "_vehicle_type",
    )

    def __init__(
        self,
        sim: SimulationContext,
        origin: RegionId,
        destination: RegionId,
        number_of_vehicles_to_charge: int,
        vehicle_type: VehicleType,
        distance_to_fleet_base: float,
        vehicle_fleet: VehicleFleet,
        state_of_charge_threshold: float,
    ) -> None:
        super().__init__(sim)
        self._config = sim.config

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_type = vehicle_type
        self._distance_to_fleet_base = distance_to_fleet_base

        self._vehicle_fleet = vehicle_fleet
        self._state_of_charge_threshold = state_of_charge_threshold

    def execute(self) -> Generator[Event, None, None]:
        """Execute batch charging: select vehicles, relocate, and charge."""
        # Get position of fleet base (centroid of hexagon)
        fleet_base_lat, fleet_base_lng = self._sim.geo_env.get_centroid(
            self._destination
        )
        fleet_base_position = GeodesicPosition(
            self._sim, fleet_base_lat, fleet_base_lng, self._destination
        )

        with self._vehicle_fleet.resource.request() as req:
            # Multiple service workers cannot access the vehicle list in parallel
            yield req

            # Identify vehicles to relocate
            potential_vehicles_to_charge: list[Vehicle] = (
                self._vehicle_fleet.vehicles_below_energy_threshold_in_region(
                    self._state_of_charge_threshold, self._origin
                )
            )
            selected_vehicles_to_charge: list[tuple[SharedVehicle, Reservation]] = []

            # Filter relevant vehicles
            for vehicle in potential_vehicles_to_charge:
                if (
                    vehicle.vehicle_type == self._vehicle_type
                    and isinstance(vehicle, SharedVehicle)
                    and len(selected_vehicles_to_charge)
                    < self._number_of_vehicles_to_charge
                    and not vehicle.is_reserved
                ):
                    reservation = vehicle.reserve()
                    selected_vehicles_to_charge.append((vehicle, reservation))

        num_vehicles = len(selected_vehicles_to_charge)

        for vehicle, reservation in selected_vehicles_to_charge:
            distance = vehicle.position << fleet_base_position
            vehicle_relocation_velocity = self._config.operators[
                0
            ].OPERATIONS_CONFIG.VEHICLE_RELOCATION_VELOCITY
            relocation_duration_per_vehicle = (
                distance / vehicle_relocation_velocity
            ) / num_vehicles

            # TODO: This is not good
            vehicle_charging_power = (
                self._config.operators[  # pyrefly: ignore[missing-attribute]
                    0
                ].OPERATIONS_CONFIG.CHARGING_STATION_POWER  # type: ignore
            )

            relocation_task = ServiceWorkerRelocationTask(
                sim=self._sim,
                vehicle=vehicle,
                destination=fleet_base_position,
                relocation_duration=relocation_duration_per_vehicle,
            )

            charging_task = FleetBaseChargingTask(
                sim=self._sim,
                vehicle=vehicle,
                charging_power=vehicle_charging_power,
                linearization_factor=num_vehicles,
            )

            session = VehicleSession(
                sim=self._sim,
                vehicle=vehicle,
                reservation=reservation,
                tasks=[relocation_task, charging_task],
                holder=None,
            )

            yield from session.execute()

        self._finished.succeed()

    def __str__(self) -> str:  # noqa: D105
        return f"FleetBaseChargingJob for {self._number_of_vehicles_to_charge} {self._vehicle_type} from {self._origin} to {self._destination} (distance = {self._distance_to_fleet_base})"

    def __repr__(self) -> str:  # noqa: D105
        return self.__str__()
