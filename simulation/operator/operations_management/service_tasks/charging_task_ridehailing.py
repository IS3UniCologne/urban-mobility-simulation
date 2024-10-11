import logging

from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.charging_station import ChargingStation
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
    TaskState,
)
from simulation.vehicle.vehicle import Vehicle, VehicleState


# TODO: refactor to not be a copy of ChargingTask that was used for SharedVehicles
class ChargingTaskRidehailing(ServiceTask):
    __slots = (
        "_origin",
        "_destination",
        "_number_of_vehicles_to_charge",
        "_vehicle_mode",
        "_distance_to_fleet_base",
        "_state_of_charge_threshold",
        "_charging_station",
        "_vehicle",
        "_waiting_time",
        "_charging_duration",
        "_kWh_charged",
        "_distance",
        "_scheduled_time",
        "_config",
    )

    def __init__(
        self,
        env: Environment,
        origin: str,
        destination: str,
        number_of_vehicles_to_charge,
        distance_to_fleet_base,
        state_of_charge_threshold,
        charging_station: ChargingStation = None,
        vehicle: Vehicle = None,
        vehicle_mode=None,
        scheduled_time=None,
    ):
        super(ChargingTaskRidehailing, self).__init__(env)

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_mode = vehicle_mode
        self._distance_to_fleet_base = distance_to_fleet_base

        self._state_of_charge_threshold = state_of_charge_threshold
        self._charging_station = charging_station
        self._vehicle = vehicle

        self._scheduled_time = scheduled_time
        self._waiting_time = None
        self._charging_duration = None
        self._kWh_charged = None
        self._distance = None
        self._config = Configuration.instance()

    @property
    def waiting_time(self):
        return self._waiting_time

    @property
    def charging_duration(self):
        return self._charging_duration

    @property
    def kWh_charged(self):
        return self._kWh_charged

    def execute(self):
        """
        Execute charging tasks
        :param simpy_env: SimPy Environment
        :return:
        """
        # Get position of fleet base (centroid of hexagon)
        geo_env = GeodesicEnvironment.getInstance()
        fleet_base_lat, fleet_base_lng = geo_env.get_centroid(self._destination)
        fleet_base_position = GeodesicPosition(
            fleet_base_lat, fleet_base_lng, self._destination
        )

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
            self._distance = vehicle.position >> fleet_base_position
            relocation_route = Edge(
                self._distance, Vertex(vehicle.position), Vertex(fleet_base_position)
            )

            self._state = TaskState.EXECUTING_RELOCATION

            # First relocate vehicle to charging site
            yield self._env.process(vehicle.relocate(relocation_route))

            if vehicle.is_electric:
                vehicle.waiting_for_charging()

                waiting_start = self._env.now

                if isinstance(self._charging_station, VirtualChargingStation):
                    # if we are in a context of shared capacity, we need to wait for the reservation

                    scheduled_timeslot_end = (
                        self._scheduled_time
                        + self._config.shared_charging_config.timeslot_duration
                    )
                    self._waiting_time = self._scheduled_time - self._env.now
                    if self._waiting_time > 0:
                        logging.debug(
                            f"Vehicle {vehicle.id} waits {self._waiting_time} minutes for reserved slot.",
                            extra={"clazz": self.__class__.__name__},
                        )
                        self._state = TaskState.EXECUTING_WAITING
                        yield self._env.timeout(max(0, self._waiting_time))
                    elif scheduled_timeslot_end <= self._env.now:
                        logging.warning(
                            "Vehicle %s arrived %s minutes at charging station after scheduled slot has ended. Cannot charge!",
                            vehicle.id,
                            self._env.now - scheduled_timeslot_end,
                            extra={"clazz": self.__class__.__name__, "oid": vehicle.id},
                        )
                        self._state = TaskState.MISSED_TIMESLOT
                        vehicle.state = VehicleState.PARKING
                        self._task_finished.succeed()
                        return

                elif (
                    len(self._charging_station.plugs.users)
                    - self._charging_station.capacity
                    == 0
                    and self._charging_station.queue_size
                    <= len(self._charging_station.plugs.queue)
                ):
                    # charging station is at capacity and the queue is also full
                    logging.info(
                        "Vehicle %s arrived charging station, but the queue is full. Cannot charge!",
                        vehicle.id,
                        extra={"clazz": self.__class__.__name__, "oid": vehicle.id},
                    )
                    self._state = TaskState.MISSED_QUEUE_FULL
                    vehicle.state = VehicleState.PARKING
                    self._task_finished.succeed()
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
                    if self._scheduled_time is not None:
                        charging_duration = min(
                            charging_duration,
                            (self._scheduled_time + 60) - self._env.now,
                        )

                    charging_duration -= 1e-6 if charging_duration > 1e-6 else 0

                    # Plugin Vehicle to Charging Station
                    vehicle.plug_to_charging_station()

                    if not isinstance(self._charging_station, VirtualChargingStation):
                        waiting_stop = self._env.now
                        self._waiting_time = waiting_stop - waiting_start

                    self._charging_duration = charging_duration
                    self._kWh_charged = charging_duration / 60 * charging_power
                    self._state = TaskState.EXECUTING_CHARGING

                    yield self._env.process(vehicle.charge(charging_duration))
            else:
                # TODO: this usage of "charge" for possibly ICE vehicles is confusing
                vehicle._state = VehicleState.PRE_SERVICE
                vehicle.plug_to_charging_station()
                yield self._env.process(vehicle.charge(charging_time=5))
            # Unplug Vehicle from Charging Station
            vehicle.unplug_from_charging_station()
            self._state = TaskState.FINISHED

        # Notify all
        self._task_finished.succeed()

    def __str__(self):
        return f"Charging Task for Vehicle {self._vehicle.id} from {self._origin} to {self._destination} (distance = {self._distance})"

    def __repr__(self):
        return self.__str__()

    def get_charging_station(self):
        pass
