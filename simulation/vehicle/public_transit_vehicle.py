from __future__ import annotations  # noqa: D100

from abc import ABC
from typing import TYPE_CHECKING

from simulation.helper.time import SimulationTimeConverter
from simulation.helper.vehicle_states import VehicleStates
from simulation.infrastructure.route import PublicTransitRoute
from simulation.vehicle.vehicle import Vehicle

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.environment.position import Position
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.infrastructure.route import PublicTransitRoute, Route
    from simulation.infrastructure.transit_network.stop import Stop
    from simulation.operator.vehicle_fleet import VehicleFleet


class PublicTransitVehicle(Vehicle, ABC):  # noqa: D101
    __slots__ = ("_current_stop", "_delay", "_route")

    def __init__(
        self,
        sim: SimulationContext,
        route: PublicTransitRoute,
        position: GeodesicPosition,
        fleet: VehicleFleet,
        vehicle_config: VehicleConfig,
    ) -> None:
        super().__init__(
            sim=sim, fleet=fleet, position=position, vehicle_config=vehicle_config
        )

        self._route: Route = route
        self._current_stop: Position = route.origin
        self._delay: int = 0  # in seconds from planned route timetable

        # Initialize state
        self._set_state(VehicleStates.AT_TERMINAL)

        self.logger.debug("Initialized.")

    @property
    def route(self) -> PublicTransitRoute:  # noqa: D102
        return self._route

    @property
    def current_stop(self) -> Stop:  # noqa: D102
        return self._current_stop

    @current_stop.setter
    def current_stop(self, stop: Stop) -> None:
        self._current_stop = stop

    @property
    def delay(self) -> int:  # noqa: D102
        return self._delay

    def prognose_arrival(self, stop: Stop) -> str:  # noqa: D102
        # TODO: this is pretty optimistic: What if the vehicle waits at intermediate stops

        distance = self._route.subroute(self._current_stop, stop).total_distance()
        duration = self.calculate_travel_time(distance)  # in minutes
        arrival = SimulationTimeConverter.as_str(self._env.now + duration, "%H:%M:%S")
        # stop will likely be reached in travel duration + delay, but not earlier than planned (will wait there)
        return max(arrival, stop.departure)
