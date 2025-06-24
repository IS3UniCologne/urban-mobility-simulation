from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import VehicleState, VehicleType
from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from tracking.tracking_interface import TrackingInterface

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.infrastructure.route import PublicTransitRoute
    from simulation.infrastructure.transit_network.route_segment import RouteSegment
    from simulation.operator.vehicle_fleet import VehicleFleet


class Bus(PublicTransitVehicle, TrackingInterface):
    bus_id = 0

    __slots__ = (
        "_config",
        "_dist_traveled",
        "_dropoffs",
        "_geo_env",
        "_has_reached_terminal",
        "_pickups",
        "_problem_config",
        "_process",
        "_spawned",
        "_time",
        "_use_learning_agent",
    )
    # Tracking
    exposes = ["_position", "state", "_available_seats"]  # noqa: RUF012

    def __init__(
        self,
        sim: SimulationContext,
        route: PublicTransitRoute,
        position: GeodesicPosition,
        fleet: VehicleFleet,
        use_learning_agent: bool,
        velocity: float,
        max_available_seats: int = 100,
    ) -> None:
        """

        :param env:
        :param position: GeodesicPosition
        :param max_available_seats: depends on type of bus
        :param velocity: e.g. 16.67 m/min * 30 (average in city)
        """
        super().__init__(
            sim, route, position, fleet, velocity, VehicleType.BUS, max_available_seats
        )

        self._id = Bus.bus_id
        self._time = SimulationTime(self._env)
        self._spawned = float(SimulationTime(self._env).now())
        Bus.bus_id += 1

        # Events
        self._has_reached_terminal = self._env.event()

        # Config
        self._config = sim.config
        self._problem_config = (
            None  # TODO: add back once dynamic problem configuration is re-implemented
        )

        # Environment / World state
        self._geo_env = sim.geo_env

        self._dropoffs = 0
        self._pickups = 0
        self._dist_traveled = 0

        # optionally, inject the run routine of a RL agent
        self._use_learning_agent = use_learning_agent

        if not self._use_learning_agent:
            # use planned route logic
            self._process = self._env.process(self._run())
        else:
            # use learning agent
            self._process = self._env.process(self._problem_config.learning_agent.run())

    def _run(self):  # noqa: ANN202
        """
        Bus Lifecycle (with planned stops, not RL agent)

        Time 12:00:00 - Departure 12:10:00 - wait
        Time 23:59:00 - Departure 00:06:00 - next_day = True - wait
        Time 00:03:00 - Departure 00:04:00 - next_day = False - wait
        Time 00:03:00 - Departure 00:04:00 - next_day = True - should not happen
        """
        while self.state is not VehicleState.AT_TERMINAL_DESTINATION:
            strf = "%H:%M:%S"
            early_arrival = (
                self._time.now_as_str() < self._current_stop.departure
                and not self._current_stop.departure_next_day
            ) or (
                self._time.now_as_str() > self._current_stop.departure
                and self._current_stop.departure_next_day
            )

            if (
                self.state is VehicleState.AT_TERMINAL_ORIGIN
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

        # # TODO: rework such that simulation is not halted when working outside of benchmark runs
        # # stop demand generation
        # self._world.stop_all_processes()
        #
        # self._has_reached_terminal.succeed((None,)*8)

        self._has_reached_terminal.succeed()

    def _move_to_next_stop(self):  # noqa: ANN202
        route_segment = self._route.route_segment_by_id(self._current_stop.stop_id)
        yield self._env.process(self.move(route_segment))

    def move(self, route_segment: RouteSegment):  # noqa: ANN201
        # TODO: use road network speed limits?

        distance = route_segment.distance  # in meter
        duration = distance / self._velocity  # in minutes

        self.state = VehicleState.EN_ROUTE_PLANNED

        self.logger.debug(
            "Bus has started driving from stop %s to stop %s.",
            route_segment.start.stop_id,
            route_segment.end.stop_id,
        )

        yield self._env.timeout(duration)

        self._current_stop = route_segment.end
        self._update_positions(route_segment.end)

        if self._current_stop == self._route.destination:
            self.state = VehicleState.AT_TERMINAL_DESTINATION
            self.logger.debug(
                "Bus has arrived at its terminal destination - stop %s at time %s",
                self._current_stop.stop_id,
                self._time.now_as_str(),
            )
        else:
            self.state = VehicleState.AT_STOP
            self.logger.debug(
                "Bus has arrived at stop %s at time %s",
                self._current_stop.stop_id,
                self._time.now_as_str(),
            )

    def _update_positions(self, new_position):  # noqa: ANN001, ANN202
        # Update Vehicle Position
        self.position = new_position

        # Update Position of Passengers
        for passenger in self._passengers:
            passenger.position = new_position

    # TODO: remove if everything works
    # @property
    # def env_state(self):
    #     return self._env_state
    #
    # def get_viable_demands(self):
    #     demands_corridor = self._geodesic_env.filter_demands_by_corridor([x.transport_task for x in self._world.users],
    #                                                                      self._corridor)
    #     demands_direction = self._geodesic_env.filter_demands_by_direction(demands_corridor, self)
    #     return demands_direction
    #
    # def _update_state(self):
    #     """
    #     This updates the state which represents the most complete picture of the environment/world the agent has at the moment
    #     """
    #
    #     # wait for external (world) or self (position) change
    #     while True:
    #         try:
    #             # TODO incorporate external change here or somewhere else again
    #             # yield simpy.events.AnyOf(self._env, [self._position_changed, self._world.changed])
    #             yield self._position_changed
    #
    #             demands = self.get_viable_demands()
    #
    #             # build OD matrix: m[start hex][end hex] = OD count for all currently known demands
    #             m = np.zeros((self._corridor_dim, self._corridor_dim), dtype=int)
    #             for d in demands:
    #                 try:
    #                     start = self._corridor_sorted.index(d.origin.get_region_id(self._action_res))
    #                     end = self._corridor_sorted.index(d.destination.get_region_id(self._action_res))
    #                     m[start][end] += 1
    #                 except ValueError as e:
    #                     self.logger.debug(
    #                         'Bus update state: Encountered demand at edge of hexagon: %s', e,
    #                         extra={"clazz": self.__class__.__name__, "oid": self._id}
    #                     )
    #                     # for now we are skipping it. I don't see a good way to solve the geometry inconsistency
    #                     continue
    #
    #             # also build "OD-demands" for each passenger in the bus:
    #             # origin = current position, destination = drop-off
    #             for p in self._seats:
    #                 try:
    #                     start = self._corridor_sorted.index(self._position.get_region_id(self._action_res))
    #                     end = self._corridor_sorted.index(p.transport_task.destination.get_region_id(self._action_res))
    #                     m[start][end] += 1
    #                 except ValueError as e:
    #                     # TODO: think about below
    #                     # if a passenger is already in the bus, the edge case must be the destination
    #                     # because the passenger can never be dropped of at the destination (with vicinity=hexagon)
    #                     # this demand should be pruned before even becoming a passenger
    #                     self.logger.debug(f'Bus update state: Encountered passenger demand at edge of hexagon: {e}',
    #                                   extra={"clazz": self.__class__.__name__, "oid": self._id})
    #                     # for now we are skipping it. I don't see a good way to solve the geometry inconsistency
    #                     continue
    #
    #             # build position vector v[hex] =1 if bus is at hex, else 0
    #             position = np.zeros(self._corridor_dim, dtype=int)
    #             pos = self._corridor_sorted.index(self._position.get_region_id(self._action_res))
    #             position[pos] = 1
    #
    #             self._env_state['position'] = position
    #             self._env_state['demands'] = m
    #             # self._env_state['drivingtime'] = int(self._time.now() - self._spawned)
    #             self._env_state['remaining_time'] = int(self._timelimit - (self._env.now - self._spawned))
    #
    #             region_id, _ = self._position.get_hexagon(self._action_res)
    #
    #             if region_id == \
    #                     self._route.destination.get_region_id(self._action_res):
    #                 self._state = VehicleState.AT_TERMINAL_DESTINATION
    #                 self.logger.info(f'Bus has arrived at its terminal destination at time {self._time.now_as_str()}',
    #                              extra={"clazz": self.__class__.__name__, "oid": self._id})
    #         except simpy.Interrupt:
    #             # stop process loop
    #             break
    #
    # def _update_reward(self, before_state):
    #
    #     # wait for action
    #     action = yield self._action_taken
    #
    #     self._rl_agent.reward = self._rl_agent.reward_state(self._env_state,
    #                                                         self._state == VehicleState.AT_TERMINAL_DESTINATION)
    #     self._rl_agent.reward_sum = self._rl_agent.reward_sum + self._rl_agent.reward
    #
    #     self.logger.debug(f'Current reward: {self._rl_agent.reward}, overall reward: {self._rl_agent.reward_sum}',
    #                   extra={"clazz": self.__class__.__name__, "oid": self._id})
    #
    #     self._agent_completed_step.succeed((before_state, action, self._rl_agent.reward, self._rl_agent.reward_sum))
    #     self._agent_completed_step = self._env.event()

    def __str__(self):  # noqa: ANN204
        return f"I have {len(self._passengers)} passengers on boards"

    def dump(self, exposed_only: bool = True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            dump_attr = [
                "state",
                "_position",
                "_available_seats",
                "_spawned",
                "_velocity",
            ]
            return {x: self.get(x) for x in dump_attr}
