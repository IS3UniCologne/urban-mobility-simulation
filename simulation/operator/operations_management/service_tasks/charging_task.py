from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import ServiceTask
from simulation.vehicle.vehicle import VehicleState


class ChargingTask(ServiceTask):

    def __init__(self, origin, destination, number_of_vehicles_to_charge, vehicle_mode,
                 distance_to_fleet_base, vehicle_fleet, state_of_charge_threshold):
        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_mode = vehicle_mode
        self._distance_to_fleet_base = distance_to_fleet_base

        self._vehicle_fleet = vehicle_fleet
        self._state_of_charge_threshold = state_of_charge_threshold

    def execute(self, simpy_env, *args):
        """
            Execute charging tasks
        :param simpy_env: SimPy Environment
        :param args: None 
        :return:
        """

        # Get position of fleet base (centroid of hexagon)
        geo_env = GeodesicEnvironment.getInstance()
        fleet_base_lat, fleet_base_lng = geo_env.get_centroid(self._destination)
        fleet_base_position = GeodesicPosition(fleet_base_lat, fleet_base_lng, self._destination)

        # Identify vehicles to relocate
        potential_vehicles_to_charge = self._vehicle_fleet.get_all_vehicles_below_soc_level_in_region(self._state_of_charge_threshold, self._origin)
        selected_vehicles_to_charge = []

        # Filter relevant vehicles
        for vehicle in potential_vehicles_to_charge:
            # Filter by vehicle mode and only parking vehicles (possibly some vehicles are driving around with low soc)
            if vehicle.__class__.__name__ == self._vehicle_mode and vehicle.state == VehicleState.PARKING:
                # Add to charging list
                selected_vehicles_to_charge.append(vehicle)

        # Start Charging Process
        for vehicle in selected_vehicles_to_charge:
            # Relocation Route from origin of vehicle to fleet base
            distance = vehicle.position >> fleet_base_position
            relocation_route = Edge(distance, Vertex(vehicle.position), Vertex(fleet_base_position))

            # First relocate vehicle to base
            yield simpy_env.process(vehicle.relocate(relocation_route, 5))

            # Plugin Vehicle to Charging Station
            vehicle.plug_to_charging_station()
            # Charge Vehicle
            yield simpy_env.process(vehicle.charge(5))

            # Unplug Vehicle from Charging Station
            vehicle.unplug_from_charging_station()
