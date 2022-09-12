from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import ServiceTask
from simulation.vehicle.vehicle import VehicleState


class ChargingTaskRidehailing(ServiceTask):

    def __init__(self, env: Environment, origin, destination, number_of_vehicles_to_charge, vehicle_mode,
                 distance_to_fleet_base, vehicle_fleet, state_of_charge_threshold, charging_station=None):

        super(ChargingTaskRidehailing, self).__init__(env)

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_mode = vehicle_mode
        self._distance_to_fleet_base = distance_to_fleet_base

        self._vehicle_fleet = vehicle_fleet
        self._state_of_charge_threshold = state_of_charge_threshold
        self._charging_station = charging_station

    def execute(self, *args):
        """
            Execute charging tasks
        :param simpy_env: SimPy Environment
        :param args: args[0] typically service worker id
        :return:
        """

        # Get position of fleet base (centroid of hexagon)
        geo_env = GeodesicEnvironment.getInstance()
        fleet_base_lat, fleet_base_lng = geo_env.get_centroid(self._destination)
        fleet_base_position = GeodesicPosition(fleet_base_lat, fleet_base_lng, self._destination)

        # with self._vehicle_fleet.resource.request() as req:
        with self._charging_station.plugs.request() as req:
            """Multiple Service Workers (within same hexagon) cannot access the vehicle list in parallel"""
            # We mark vehilces which are already scheduled using (prepare_for_service_task) in a thread safe way
            yield req

            # Identify vehicles to relocate
            potential_vehicles_to_charge = self._vehicle_fleet.get_all_vehicles_below_soc_level_in_region(self._state_of_charge_threshold, self._origin)
            selected_vehicles_to_charge = []

            # Filter relevant vehicles
            for vehicle in potential_vehicles_to_charge:
                # Filter by vehicle mode and only parking vehicles (possibly some vehicles are driving around with low soc)
                if (vehicle.__class__.__name__ == self._vehicle_mode
                        and vehicle.state == VehicleState.PARKING
                        and len(selected_vehicles_to_charge) < self._number_of_vehicles_to_charge):
                    # Mark Vehicle => Change state su
                    # ch that other service workers don't touch it!!
                    vehicle.prepare_for_service_task(f"Service Worker {args[0]}", self.__class__.__name__)
                    # Add to charging list
                    selected_vehicles_to_charge.append(vehicle)

        # Start Charging Process
        for vehicle in selected_vehicles_to_charge:
            # Relocation Route from origin of vehicle to fleet base
            distance = vehicle.position >> fleet_base_position
            relocation_route = Edge(distance, Vertex(vehicle.position), Vertex(fleet_base_position))

            # Note, we divide the duration by the number of vehicles to "linearize" the service time
            # In the real world, these processes would be in parallel rather than in a linear fashion
            # However, the total duration of both approaches (parallel, linearized) coincides.
            # Thus, we ensure that the service workers spends the same amount of time as in the parallel case.
            vehicle_relocation_velocity = Configuration.instance().shared_vehicle_operator_config.vehicle_relocation_velocity
            relocation_duration_per_vehicle = (distance/vehicle_relocation_velocity)/len(selected_vehicles_to_charge)

            # First relocate vehicle to base
            yield self._env.process(vehicle.relocate(relocation_route, relocation_duration_per_vehicle, f"Service Worker {args[0]}"))

            # Plugin Vehicle to Charging Station
            vehicle.plug_to_charging_station()

            # Charge Vehicle
            vehicle_charging_power = Configuration.instance().shared_vehicle_operator_config.charging_station_power
            # Note: See text regarding linearization
            # *60 as state of charge is in kWh => kWmin
            charging_duration_per_vehicles = ((vehicle._max_state_of_charge / vehicle_charging_power)*60)/len(selected_vehicles_to_charge)

            yield self._env.process(vehicle.charge(charging_duration_per_vehicles))

            # Unplug Vehicle from Charging Station
            vehicle.unplug_from_charging_station()

        # Notify all
        self._task_finished.succeed()

        # Notify all
        self._task_finished = self._env.event()

    def __str__(self):
        return f"Charging Task for {self._number_of_vehicles_to_charge} {self._vehicle_mode} from {self._origin} to {self._destination} (distance = {self._distance_to_fleet_base})"

    def __repr__(self):
        return self.__str__()

    def get_charging_station(self):
        pass
