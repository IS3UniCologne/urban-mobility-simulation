from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from beartype.door import is_bearable

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleState
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
    TaskState,
)

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.infrastructure.charging_stations.charging_station import (
        ChargingStation,
    )
    from simulation.vehicle.vehicle import Vehicle


# TODO: refactor to not be a copy of ChargingTask that was used for SharedVehicles
class ChargingTaskRidehailing(ServiceTask):  # noqa: D101
    __slots__ = (
        "_arrived_at_charging_station",
        "_charging_duration",
        "_charging_station",
        "_destination",
        "_destination_position",
        "_distance",
        "_distance_to_fleet_base",
        "_estimated_arrival_time",
        "_estimated_completion_time",
        "_geo_env",
        "_kWh_charged",
        "_number_of_vehicles_to_charge",
        "_origin",
        "_scheduled_time",
        "_started_charging",
        "_state",
        "_state_of_charge_threshold",
        "_vehicle",
        "_vehicle_type",
        "_waiting_time",
    )

    def __init__(
        self,
        sim: SimulationContext,
        origin: str,
        destination: str,
        number_of_vehicles_to_charge: int,
        distance_to_fleet_base: float,
        state_of_charge_threshold: float,
        charging_station: ChargingStation = None,
        vehicle: Vehicle = None,
        vehicle_type=None,  # noqa: ANN001
        scheduled_time=None,  # noqa: ANN001
    ) -> None:
        super().__init__(sim)

        self._geo_env = sim.geo_env
        self._origin = origin
        self._destination = destination
        self._destination_position = GeodesicPosition(
            sim, *self._geo_env.get_centroid(self._destination), self._destination
        )
        self._number_of_vehicles_to_charge = number_of_vehicles_to_charge
        self._vehicle_type = vehicle_type
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

        # Events
        self._arrived_at_charging_station = self._env.event()
        self._started_charging = self._env.event()

    @property
    def destination(self):  # noqa: ANN201, D102
        return self._destination

    @property
    def waiting_time(self):  # noqa: ANN201, D102
        return self._waiting_time

    @property
    def charging_duration(self):  # noqa: ANN201, D102
        return self._charging_duration

    @property
    def kWh_charged(self):  # noqa: ANN201, D102
        return self._kWh_charged

    def execute(self):  # noqa: ANN201
        """
        Execute charging tasks
        :param simpy_env: SimPy Environment
        :return:
        """  # noqa: D202, D205, D400

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
                            + self._charging_station.virtual_charging_infrastructure._charging_infrastructure._charging_infra_config.COORDINATION_TIMESLOT_DURATION  # noqa: SLF001
                        )
                        self._waiting_time = self._scheduled_time - self._env.now
                        if self._waiting_time > 0:
                            self.logger.debug(
                                "Vehicle %s waits %s minutes for reserved slot.",
                                self._vehicle.uid,
                                self._waiting_time,
                            )
                            self._state = TaskState.EXECUTING_WAITING
                            yield self._env.timeout(max(0, self._waiting_time))
                        elif scheduled_timeslot_end <= self._env.now:
                            self.logger.warning(
                                "Vehicle %s arrived %s minutes at charging station after scheduled slot has ended. Cannot charge!",
                                self._vehicle.uid,
                                self._env.now - scheduled_timeslot_end,
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
                    self.logger.info(
                        "Vehicle %s arrived charging station, but the queue is full. Cannot charge!",
                        self._vehicle.uid,
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
                                + self._charging_station.virtual_charging_infrastructure._charging_infrastructure._charging_infra_config.COORDINATION_TIMESLOT_DURATION  # noqa: SLF001
                            )
                            - self._env.now,
                        )

                    if self._charging_duration <= 0:
                        self.logger.info(
                            "Vehicle %s has a fishy charging time of %s minutes at. Cannot charge!",
                            self._vehicle.uid,
                            self._charging_duration,
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

    def __str__(self):  # noqa: ANN204, D105
        return f"Charging Task for Vehicle {self._vehicle.uid} from {self._origin} to {self._destination} (distance = {self._distance})"

    def __repr__(self):  # noqa: ANN204, D105
        return self.__str__()

    def get_charging_station(self):  # noqa: ANN201, D102
        pass
