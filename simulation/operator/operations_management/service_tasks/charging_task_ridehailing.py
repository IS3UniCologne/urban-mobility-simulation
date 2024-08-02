import logging

from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
)
from simulation.vehicle.vehicle import VehicleState


# TODO: refactor to not be a copy of ChargingTask that was used for SharedVehicles
class ChargingTaskRidehailing(ServiceTask):
    __slots = (
        "_origin",
        "_destination",
        "_number_of_vehicles_to_charge",
        "_vehicle_mode",
        "_distance_to_fleet_base",
        "_vehicle_fleet",
        "_state_of_charge_threshold",
        "_charging_station",
        "_vehicle",
    )

    def __init__(
        self,
        env: Environment,
        origin,
        destination,
        number_of_vehicles_to_charge,
        distance_to_fleet_base,
        vehicle_fleet,
        state_of_charge_threshold,
        charging_station=None,
        vehicle=None,
        vehicle_mode=None,
    ):
        super(ChargingTaskRidehailing, self).__init__(env)

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_mode = vehicle_mode
        self._distance_to_fleet_base = distance_to_fleet_base

        self._vehicle_fleet = vehicle_fleet
        self._state_of_charge_threshold = state_of_charge_threshold
        self._charging_station = charging_station
        self._vehicle = vehicle

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
        fleet_base_position = GeodesicPosition(
            fleet_base_lat, fleet_base_lng, self._destination
        )

        # with self._vehicle_fleet.resource.request() as req:

        # Identify vehicles to relocate
        potential_vehicles_to_charge = [self._vehicle]
        selected_vehicles_to_charge = []
        # TODO: remove the need for service worker to relocate
        # Filter relevant vehicles

        for vehicle in potential_vehicles_to_charge:
            # Filter by vehicle mode and only parking vehicles (possibly some vehicles are driving around with low soc)
            if (
                vehicle.state == VehicleState.PARKING
                and len(selected_vehicles_to_charge)
                < self._number_of_vehicles_to_charge
            ):
                # Add to charging list
                selected_vehicles_to_charge.append(vehicle)

        # Start Charging Process
        for vehicle in selected_vehicles_to_charge:
            # Relocation Route from origin of vehicle to fleet base
            distance = vehicle.position >> fleet_base_position
            relocation_route = Edge(
                distance, Vertex(vehicle.position), Vertex(fleet_base_position)
            )

            vehicle_relocation_velocity = Configuration.instance().ridehailing_operator_config.vehicle_relocation_velocity
            relocation_duration_per_vehicle = (
                distance / vehicle_relocation_velocity
            ) / len(selected_vehicles_to_charge)

            # First relocate vehicle to charging site
            yield self._env.process(
                vehicle.relocate(relocation_route, relocation_duration_per_vehicle)
            )

            scheduled_time = None

            if vehicle.is_electric:
                vehicle.waiting_for_charging()

                if isinstance(self._charging_station, VirtualChargingStation):
                    # if we are in a context of shared capacity, we need to wait for the reservation
                    scheduled_time = self._charging_station.valid_timeframe[0]
                    if scheduled_time - self._env.now > 0:
                        logging.debug(
                            f"Vehicle {vehicle.id} waits {scheduled_time - self._env.now} minutes for reserved slot.",
                            extra={"clazz": self.__class__.__name__},
                        )
                        yield self._env.timeout(max(0, scheduled_time - self._env.now))
                    elif scheduled_time - self._env.now < 0:
                        logging.warning(
                            "Vehicle %s arrived %s minutes at charging station after scheduled slot has ended. Cannot charge!",
                            vehicle.id,
                            self._env.now - scheduled_time,
                            extra={"clazz": self.__class__.__name__, "oid": vehicle.id},
                        )
                        return

                with self._charging_station.plugs.request() as req:
                    yield req

                    # Charge Vehicle
                    vehicle_charging_power = self._charging_station.power
                    charging_power = min(
                        vehicle_charging_power, self._charging_station.power
                    )
                    # Note: See text regarding linearization
                    # *60 as state of charge is in kWh => kWmin
                    charging_duration = (
                        (vehicle.max_state_of_charge - vehicle.current_state_of_charge)
                        / charging_power
                        * 60
                    )
                    if scheduled_time is not None:
                        charging_duration = min(
                            charging_duration, (scheduled_time + 60) - self._env.now
                        )

                    # Plugin Vehicle to Charging Station
                    vehicle.plug_to_charging_station()

                    yield self._env.process(vehicle.charge(charging_duration))
            else:
                # TODO: this usage of "charge" for possibly ICE vehicles is confusing
                vehicle._state = VehicleState.PRE_SERVICE
                vehicle.plug_to_charging_station()
                yield self._env.process(vehicle.charge(charging_time=5))
            # Unplug Vehicle from Charging Station
            vehicle.unplug_from_charging_station()
        # Notify all
        self._task_finished.succeed()
        # Notify all
        self._task_finished = self._env.event()

    def __str__(self):
        return f"Charging Task for {self._number_of_vehicles_to_charge} from {self._origin} to {self._destination} (distance = {self._distance_to_fleet_base})"

    def __repr__(self):
        return self.__str__()

    def get_charging_station(self):
        pass
