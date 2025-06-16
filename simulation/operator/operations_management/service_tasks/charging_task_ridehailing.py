import logging

from beartype.door import is_bearable
from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import VehicleState
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
from simulation.vehicle.vehicle import Vehicle


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
        "_estimated_arrival_time",
        "_estimated_completion_time",
        "_kWh_charged",
        "_distance",
        "_scheduled_time",
        "_config",
    )

    def __init__(  # noqa: ANN204
        self,
        env: Environment,
        origin: str,
        destination: str,
        number_of_vehicles_to_charge,  # noqa: ANN001
        distance_to_fleet_base,  # noqa: ANN001
        state_of_charge_threshold,  # noqa: ANN001
        charging_station: ChargingStation = None,
        vehicle: Vehicle = None,
        vehicle_mode=None,  # noqa: ANN001
        scheduled_time=None,  # noqa: ANN001
    ):
        super(ChargingTaskRidehailing, self).__init__(env)  # noqa: UP008

        _geo_env = GeodesicEnvironment.getInstance()
        self._origin = origin
        self._destination = destination
        self._destination_position = GeodesicPosition(
            *_geo_env.get_centroid(self._destination), self._destination
        )
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_mode = vehicle_mode
        self._distance_to_fleet_base = distance_to_fleet_base

        self._state_of_charge_threshold = state_of_charge_threshold
        self._charging_station = charging_station
        self._vehicle = vehicle

        self._scheduled_time = scheduled_time
        self._estimated_arrival_time = (
            self._env.now
            + (vehicle.position >> self._destination_position) / self._vehicle.velocity
        )
        self._waiting_time = None
        self._charging_duration = (
            (
                vehicle.max_state_of_charge
                - vehicle.current_state_of_charge
                + (
                    (vehicle.position >> self._destination_position)
                    / 1000
                    * vehicle._energy_consumption  # noqa: SLF001
                )
            )
            / charging_station.power
            * 60
        )
        self._estimated_completion_time = None
        self._kWh_charged = None
        self._distance = vehicle.position >> self._destination_position
        self._config = Configuration()

        # Events
        self._arrived_at_charging_station = self._env.event()
        self._started_charging = self._env.event()

    @property
    def destination(self):  # noqa: ANN201
        return self._destination

    @property
    def waiting_time(self):  # noqa: ANN201
        return self._waiting_time

    @property
    def charging_duration(self):  # noqa: ANN201
        return self._charging_duration

    @property
    def kWh_charged(self):  # noqa: ANN201
        return self._kWh_charged

    def execute(self):  # noqa: ANN201
        """
        Execute charging tasks
        :param simpy_env: SimPy Environment
        :return:
        """

        # Filter only parking vehicles (possibly some vehicles are driving around with low soc)
        if self._vehicle.state == VehicleState.PARKING:
            relocation_route = Edge(
                self._distance,
                Vertex(self._vehicle.position),
                Vertex(self._destination_position),
            )

            self._state = TaskState.EXECUTING_RELOCATION

            # First relocate vehicle to charging site
            yield self._env.process(self._vehicle.relocate(relocation_route))

            if self._vehicle.is_electric:
                self._vehicle.waiting_for_charging()
                waiting_start = self._env.now

                if is_bearable(self._charging_station, VirtualChargingStation):
                    # only in this case we can check for the next condition, otherwise AttributeError gets thrown
                    if self._charging_station.valid_timeframe is not None:
                        # if we are in a context of shared capacity, we need to wait for the reservation

                        scheduled_timeslot_end = (
                            self._scheduled_time
                            + self._config.shared_charging_auction.TIMESLOT_DURATION
                        )
                        self._waiting_time = self._scheduled_time - self._env.now
                        if self._waiting_time > 0:
                            logging.debug(
                                "Vehicle %s waits %s minutes for reserved slot.",
                                self._vehicle.id,
                                self._waiting_time,
                                extra={"clazz": self.__class__.__name__},
                            )
                            self._state = TaskState.EXECUTING_WAITING
                            yield self._env.timeout(max(0, self._waiting_time))
                        elif scheduled_timeslot_end <= self._env.now:
                            logging.warning(
                                "Vehicle %s arrived %s minutes at charging station after scheduled slot has ended. Cannot charge!",
                                self._vehicle.id,
                                self._env.now - scheduled_timeslot_end,
                                extra={
                                    "clazz": self.__class__.__name__,
                                    "oid": self._vehicle.id,
                                },
                            )
                            self._state = TaskState.MISSED_TIMESLOT
                            self._vehicle.state = VehicleState.PARKING
                            self._task_finished.succeed()
                            return

                check_station_full = False
                # we sanity check if the physical capacity is not exhausted
                check_station_full = (
                    len(self._charging_station.plugs.users)
                    >= self._charging_station.plugs.capacity
                )

                if check_station_full and self._charging_station.queue_size <= len(
                    self._charging_station.plugs.queue
                ):
                    # charging station is at capacity and the queue is also full
                    logging.info(
                        "Vehicle %s arrived charging station, but the queue is full. Cannot charge!",
                        self._vehicle.id,
                        extra={
                            "clazz": self.__class__.__name__,
                            "oid": self._vehicle.id,
                        },
                    )
                    self._state = TaskState.MISSED_QUEUE_FULL
                    self._vehicle.state = VehicleState.PARKING
                    self._task_finished.succeed()
                    return
                else:
                    self._state = TaskState.EXECUTING_WAITING

                with self._charging_station.plugs.request() as req:
                    yield req

                    if self._scheduled_time is not None:
                        self._charging_duration = min(
                            self._charging_duration,
                            (
                                self._scheduled_time
                                + self._config.shared_charging_auction.TIMESLOT_DURATION
                            )
                            - self._env.now,
                        )

                    if self._charging_duration <= 0:
                        logging.info(
                            "Vehicle %s has a fishy charging time of %s minutes at. Cannot charge!",
                            self._vehicle.id,
                            self._charging_duration,
                            extra={
                                "clazz": self.__class__.__name__,
                                "oid": self._vehicle.id,
                            },
                        )
                        self._state = TaskState.MISSED_TIMESLOT
                        self._vehicle.state = VehicleState.PARKING
                        self._task_finished.succeed()
                        return

                    self._charging_duration -= (
                        1e-6 if self._charging_duration > 1e-6 else 0
                    )

                    self._kWh_charged = (
                        self._charging_duration / 60 * self._charging_station.power
                    )
                    self._estimated_completion_time = (
                        self._env.now + self._charging_duration
                    )

                    # Plugin Vehicle to Charging Station
                    self._arrived_at_charging_station.succeed()
                    self._vehicle.plug_to_charging_station()
                    self._env.process(self._charging_station.plug_in_notify())

                    if not isinstance(self._charging_station, VirtualChargingStation):
                        waiting_stop = self._env.now
                        self._waiting_time = waiting_stop - waiting_start

                    self._state = TaskState.EXECUTING_CHARGING

                    self._started_charging.succeed(self._env.now)

                    yield self._env.process(
                        self._vehicle.charge(self._charging_duration, self._kWh_charged)
                    )
            else:
                # TODO: this usage of "charge" for possibly ICE vehicles is confusing
                self._vehicle.state = VehicleState.PRE_SERVICE
                self._vehicle.plug_to_charging_station()
                yield self._env.process(self._vehicle.charge(charging_time=5))
            # Unplug Vehicle from Charging Station
            self._vehicle.unplug_from_charging_station()
            self._env.process(self._charging_station.plug_out_notify())
            self._state = TaskState.FINISHED

        # Notify all
        self._task_finished.succeed()

    def __str__(self):  # noqa: ANN204
        return f"Charging Task for Vehicle {self._vehicle.id} from {self._origin} to {self._destination} (distance = {self._distance})"

    def __repr__(self):  # noqa: ANN204
        return self.__str__()

    def get_charging_station(self):  # noqa: ANN201
        pass
