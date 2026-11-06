from __future__ import annotations  # noqa: D100

from datetime import datetime
from typing import TYPE_CHECKING

from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.helper.vehicle_states import VehicleStates
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import (
        Configuration,
        VehicleConfig,
    )
    from simulation.infrastructure.route import PublicTransitRoute
    from simulation.infrastructure.transit_network.route_segment import RouteSegment
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.movement_stats import MovementStats


class Bus(PublicTransitVehicle):
    """
    Bus that drives one public transit route along its scheduled stops.

    The constructor starts the process that drives the bus.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    route : PublicTransitRoute
        Route to drive, from origin to terminal.
    position : GeodesicPosition
        Initial position.
    fleet : VehicleFleet
        Fleet the bus belongs to.
    vehicle_config : VehicleConfig
        Vehicle configuration.

    Attributes
    ----------
    bus_id : int
        Id of the next bus, shared by all buses and counted up on each construction.
    """

    bus_id: int = 0

    __slots__ = ("_config", "_geo_env", "_has_reached_terminal", "_process", "_time")

    def __init__(
        self,
        sim: SimulationContext,
        route: PublicTransitRoute,
        position: GeodesicPosition,
        fleet: VehicleFleet,
        vehicle_config: VehicleConfig,
    ) -> None:
        super().__init__(sim, route, position, fleet, vehicle_config)

        self._id = Bus.bus_id
        self._time = SimulationTime(self._env)
        Bus.bus_id += 1

        # Events
        self._has_reached_terminal: Event = self._env.event()

        # Config
        self._config: Configuration = sim.config

        # Environment / World state
        self._geo_env = sim.geo_env

        self._process: Event = self._env.process(self._run())

    def _run(self) -> Generator[Event, None, None]:
        """Drive the bus along its scheduled stops until it reaches the terminal.

        Time 12:00:00 - Departure 12:10:00 - wait
        Time 23:59:00 - Departure 00:06:00 - next_day = True - wait
        Time 00:03:00 - Departure 00:04:00 - next_day = False - wait
        Time 00:03:00 - Departure 00:04:00 - next_day = True - should not happen
        """
        while self.state is not VehicleStates.AT_TERMINAL:
            strf = "%H:%M:%S"
            early_arrival = (
                self._time.now_as_str() < self._current_stop.departure
                and not self._current_stop.departure_next_day
            ) or (
                self._time.now_as_str() > self._current_stop.departure
                and self._current_stop.departure_next_day
            )

            if (
                self.state is VehicleStates.AT_TERMINAL
                and self._time.now_as_str() < self._current_stop.departure
            ):
                # bus was pre-initialized by transit operator
                wait = SimulationTimeConverter.duration_between(
                    self._time.now_as_str(strf), self._current_stop.departure, strf
                )
                self.logger.debug(
                    "Bus waits for scheduled departure from terminal origin"
                )
                yield self._env.timeout(wait)

            elif early_arrival:
                # if the bus has reached the planned stop earlier, wait
                wait = SimulationTimeConverter.duration_between(
                    self._time.now_as_str(strf),
                    self._current_stop.departure,
                    strf,
                    self._current_stop.departure_next_day,
                )
                self.logger.debug(
                    "Bus is ahead of schedule and will wait for scheduled departure."
                )
                self._delay = 0  # reset delay
                yield self._env.timeout(wait)

            elif (
                self._time.now_as_str() > self._current_stop.departure
                and not self._current_stop.departure_next_day
            ):
                # if the bus has reached the planned stop late, set delay
                diff = datetime.strptime(
                    self._time.now_as_str(strf), strf
                ) - datetime.strptime(self._current_stop.departure, strf)
                self._delay = diff.total_seconds()

            # otherwise move on with driving
            yield self._env.process(self._move_to_next_stop())

        self._has_reached_terminal.succeed()

    def _move_to_next_stop(self) -> Generator[Event, None, None]:
        route_segment = self._route.route_segment_by_id(self._current_stop.stop_id)
        yield self._env.process(self._move(route_segment))

    def _move(
        self, route_segment: RouteSegment
    ) -> Generator[Event, None, MovementStats]:
        # TODO: use road network speed limits?

        self._set_state(VehicleStates.EN_ROUTE)

        self.logger.debug(
            "Bus has started driving from stop %s to stop %s.",
            route_segment.start.stop_id,
            route_segment.end.stop_id,
        )

        stats = yield from super()._move(route_segment)

        self._current_stop = route_segment.end

        if self._current_stop == self._route.destination:
            self._set_state(VehicleStates.AT_TERMINAL)
            self.logger.debug(
                "Bus has arrived at its terminal destination - stop %s at time %s",
                self._current_stop.stop_id,
                self._time.now_as_str(),
            )
        else:
            self._set_state(VehicleStates.AT_STOP)
            self.logger.debug(
                "Bus has arrived at stop %s at time %s",
                self._current_stop.stop_id,
                self._time.now_as_str(),
            )

        return stats

    def _update_position(self, new_position: GeodesicPosition) -> None:
        # Update Vehicle Position
        self.position = new_position

        # Update Position of Passengers
        for passenger in self._passengers:
            passenger.on_vehicle_moved(new_position)

    def __str__(self) -> str:
        """Describe the bus by its passenger count."""
        return f"I have {len(self._passengers)} passengers on boards"
