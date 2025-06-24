from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import VehicleState, VehicleType
from simulation.helper.time import SimulationTimeConverter
from simulation.vehicle.vehicle import Vehicle

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.position import Position
    from simulation.infrastructure.route import PublicTransitRoute
    from simulation.infrastructure.transit_network.stop import Stop
    from simulation.operator.vehicle_fleet import VehicleFleet


class PublicTransitVehicleException(Exception):
    pass


class PublicTransitVehicleFull(PublicTransitVehicleException):
    pass


class PublicTransitVehicle(Vehicle, ABC):
    __slots__ = ("_current_stop", "_delay", "_route")

    def __init__(
        self,
        sim: SimulationContext,
        route: PublicTransitRoute,
        position: Position,
        fleet: VehicleFleet,
        velocity: float,
        vehicle_type: VehicleType,
        max_available_seats: int,
    ) -> None:
        super().__init__(
            sim=sim,
            fleet=fleet,
            position=position,
            velocity=velocity,
            vehicle_type=vehicle_type,
            max_available_seats=max_available_seats,
        )

        self._route = route
        self._current_stop = route.origin
        self._delay = 0  # in seconds from planned route timetable

        # Initialize state
        self.state = VehicleState.AT_TERMINAL_ORIGIN

        self.logger.debug("Initialized.")

    @property
    def route(self):  # noqa: ANN201
        return self._route

    @property
    def current_stop(self):  # noqa: ANN201
        return self._current_stop

    @current_stop.setter
    def current_stop(self, stop: Stop):  # noqa: ANN202
        self._current_stop = stop

    @property
    def delay(self):  # noqa: ANN201
        return self._delay

    def prognose_arrival(self, stop: Stop):  # noqa: ANN201
        # TODO: this is pretty optimistic: What if the vehicle waits at intermediate stops

        distance = self._route.subroute(self._current_stop, stop).total_distance()
        duration = distance / self._velocity  # in minutes
        arrival = SimulationTimeConverter.as_str(self._env.now + duration, "%H:%M:%S")
        # stop will likely be reached in travel duration + delay, but not earlier than planned (will wait there)
        return max(arrival, stop.departure)
