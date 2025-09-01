from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleState, VehicleType
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
)

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.vehicle_fleet import VehicleFleet


class ChargingTask(ServiceTask):  # noqa: D101
    __slots__ = (
        "_config",
        "_destination",
        "_distance_to_fleet_base",
        "_number_of_vehicles_to_charge",
        "_origin",
        "_sim",
        "_state_of_charge_threshold",
        "_vehicle_fleet",
        "_vehicle_type",
    )

    def __init__(
        self,
        sim: SimulationContext,
        origin: GeodesicPosition,
        destination: GeodesicPosition,
        number_of_vehicles_to_charge: int,
        vehicle_type: VehicleType,
        distance_to_fleet_base: float,
        vehicle_fleet: VehicleFleet,
        state_of_charge_threshold: float,
    ) -> None:
        super().__init__(sim)
        self._sim = sim
        self._config = sim.config

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_type = vehicle_type
        self._distance_to_fleet_base = distance_to_fleet_base

        self._vehicle_fleet = vehicle_fleet
        self._state_of_charge_threshold = state_of_charge_threshold

    def execute(self, *args):  # noqa: ANN002, ANN201
        """
            Execute charging tasks
        :param simpy_env: SimPy Environment
        :param args: args[0] typically service worker id
        :return:
        """  # noqa: D202, D205, D400

        # Get position of fleet base (centroid of hexagon)
        fleet_base_lat, fleet_base_lng = self._sim.geo_env.get_centroid(
            self._destination
        )
        fleet_base_position = GeodesicPosition(
            self._sim, fleet_base_lat, fleet_base_lng, self._destination
        )

        with self._vehicle_fleet.resource.request() as req:
            """Multiple Service Workers (within same hexagon) cannot access the vehicle list in parallel"""
            # We mark vehilces which are already scheduled using (prepare_for_service_task) in a thread safe way
            yield req

            # Identify vehicles to relocate
            potential_vehicles_to_charge = (
                self._vehicle_fleet.vehicles_below_soc_threshold_in_region(
                    self._state_of_charge_threshold, self._origin
                )
            )
            selected_vehicles_to_charge = []

            # Filter relevant vehicles
            for vehicle in potential_vehicles_to_charge:
                # Filter by vehicle mode and only parking vehicles (possibly some vehicles are driving around with low soc)
                if (
                    vehicle.vehicle_type == self._vehicle_type
                    and vehicle.state == VehicleState.PARKING
                    and len(selected_vehicles_to_charge)
                    < self._number_of_vehicles_to_charge
                ):
                    # Mark Vehicle => Change state su
                    # ch that other service workers don't touch it!!
                    vehicle.prepare_for_service_task(
                        f"Service Worker {args[0]}", self.__class__.__name__
                    )
                    # Add to charging list
                    selected_vehicles_to_charge.append(vehicle)

        # Start Charging Process
        for vehicle in selected_vehicles_to_charge:
            # Relocation Route from origin of vehicle to fleet base
            distance = vehicle.position >> fleet_base_position
            relocation_route = Edge(
                distance, Vertex(vehicle.position), Vertex(fleet_base_position)
            )

            # Note, we divide the duration by the number of vehicles to "linearize" the service time
            # In the real world, these processes would be in parallel rather than in a linear fashion
            # However, the total duration of both approaches (parallel, linearized) coincides.
            # Thus, we ensure that the service workers spends the same amount of time as in the parallel case.
            vehicle_relocation_velocity = self._config.operators[
                0
            ].OPERATIONS_CONFIG.VEHICLE_RELOCATION_VELOCITY
            relocation_duration_per_vehicle = (
                distance / vehicle_relocation_velocity
            ) / len(selected_vehicles_to_charge)

            # First relocate vehicle to base
            yield self._env.process(
                vehicle.relocate(
                    relocation_route,
                    relocation_duration_per_vehicle,
                    f"Service Worker {args[0]}",
                )
            )

            # Plugin Vehicle to Charging Station
            vehicle.plug_to_charging_station()

            # Charge Vehicle
            vehicle_charging_power = self._config.operators[0].CHARGING_STATION_POWER
            # Note: See text regarding linearization
            # *60 as state of charge is in kWh => kWmin
            charging_duration_per_vehicles = (
                (vehicle._max_state_of_charge / vehicle_charging_power) * 60  # noqa: SLF001
            ) / len(selected_vehicles_to_charge)

            yield self._env.process(vehicle.charge(charging_duration_per_vehicles))

            # Unplug Vehicle from Charging Station
            vehicle.unplug_from_charging_station()

        # Notify all
        self._task_finished.succeed()

        # Notify all
        self._task_finished = self._env.event()

    def __str__(self):  # noqa: ANN204, D105
        return f"Charging Task for {self._number_of_vehicles_to_charge} {self._vehicle_type} from {self._origin} to {self._destination} (distance = {self._distance_to_fleet_base})"

    def __repr__(self):  # noqa: ANN204, D105
        return self.__str__()
