from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
)
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.vehicle import VehicleState


class RelocationTask(ServiceTask):
    __slots__ = (
        "_origin",
        "_destination",
        "_number_of_vehicles_to_relocate",
        "_vehicle_mode",
        "_distance",
        "_vehicle_fleet",
    )

    def __init__(
        self,
        env: Environment,
        origin,
        destination,
        number_of_vehicles_to_relocate,
        distance,
        vehicle_mode,
        vehicle_fleet: VehicleFleet,
    ):
        super(RelocationTask, self).__init__(env)

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_relocate = number_of_vehicles_to_relocate
        self._vehicle_mode = vehicle_mode

        self._vehicle_fleet = vehicle_fleet
        self._distance = distance

    def execute(self, *args):
        # Get Spatial Environment
        geo_env = GeodesicEnvironment.getInstance()

        with self._vehicle_fleet.resource.request() as req:
            """Multiple Service Workers (within same hexagon) cannot access the vehicle list in parallel"""
            # We mark vehilces which are already scheduled using (prepare_for_service_task) in a thread safe way
            yield req

            # Identify vehicles to relocate
            potential_vehicles_to_relocate = self._vehicle_fleet.get_vehicles_in_region(
                self._origin
            )
            selected_vehicles_to_relocate = []

            # Filter relevant vehicles
            for vehicle in potential_vehicles_to_relocate:
                # Filter by vehicle mode and only parking vehicles (possibly some vehicles are driving around with low soc)
                if (
                    vehicle.__class__.__name__
                    == self._vehicle_mode  # TODO: This should not be based on the class name
                    and vehicle.state == VehicleState.PARKING
                ):
                    # Mark Vehicle => Change state su
                    # ch that other service workers don't touch it!!
                    vehicle.prepare_for_service_task(
                        f"Service Worker {args[0]}", self.__class__.__name__
                    )
                    # Add to charging list
                    selected_vehicles_to_relocate.append(vehicle)
                    if (
                        len(selected_vehicles_to_relocate)
                        >= self._number_of_vehicles_to_relocate
                    ):
                        # leave the loop if we have enough vehicles
                        break
        # Start Relocation Process
        for vehicle in selected_vehicles_to_relocate:
            # Random Destination at Dest Region
            lat, lng = geo_env.get_random_position(self._destination)
            vehicle_dest = GeodesicPosition(lat, lng, self._destination)

            # Relocation Route
            relocation_route = Edge(
                self._distance, Vertex(vehicle.position), Vertex(vehicle_dest)
            )

            # Calculate Relocation Cost based on distance, relocation velocity and number of vehicles to relocate.
            # As in the charging task, we linearize the relocation task if multiple vehicles need to be relocated.
            # Thus, we ensure that the total relocation cost corresponds to the parallel case.
            vehicle_relocation_velocity = (
                Configuration().shared_vehicle_operators[0].VEHICLE_RELOCATION_VELOCITY
            )
            relocation_duration_per_vehicle = (
                relocation_route.distance / vehicle_relocation_velocity
            ) / len(selected_vehicles_to_relocate)

            yield self._env.process(
                vehicle.relocate(
                    relocation_route,
                    relocation_duration_per_vehicle,
                    f"Service Worker {args[0]}",
                )
            )

        # Notify all
        self._task_finished.succeed()

        # Notify all
        self._task_finished = self._env.event()

    def __str__(self):
        return f"Relocating {self._number_of_vehicles_to_relocate} {self._vehicle_mode} from {self._origin} to {self._destination} (distance = {self._distance})"

    def __repr__(self):
        return self.__str__()
