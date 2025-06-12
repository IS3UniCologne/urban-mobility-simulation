import ast
import logging

import h3
import numpy as np
from simpy import Environment

from learning.interface.learning_interface import LearningInterface
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import VehicleState
from simulation.helper.time import SimulationTimeConverter
from simulation.world.world import World
from tracking.tracking import Tracking


class DynamicBusProblem(LearningInterface):
    """
    This class defines the Dynamic Bus Routing Problem and provides an abstraction layer that bridges the simulation and
    implementation as pure RL problem.
    """

    def __init__(self, env: Environment):  # noqa: ANN204
        super(DynamicBusProblem, self).__init__(env)  # noqa: UP008

        # Config
        self._config = Configuration()
        self._problem_config = self._config.dynamic_routing_config

        # Environment / World state
        self._geodesic_env = GeodesicEnvironment.getInstance()
        self._world = World.instance()
        self._corridor = None
        self._corridor_dim = None
        self._corridor_sorted = None

        # H3 action resolution
        self._action_res = self._config.dynamic_routing_config.action_resolution

        # Events
        self._action_taken = self.env.event()

        # Tracking
        self._tracking = Tracking.instance()

        # KPI
        self.reached_destination = False
        self.distance = 0
        self.duration = 0

        # inject bus later, when spawned by operator
        self.bus = None
        self._timelimit = None

        # TODO: should the problem define the state space? Or should a StateSpace handle this?
        self._state_size_flattened = None

    def problem_init(self):  # noqa: ANN201
        """
        This method is only called after the problem has been assigned a bus
        Then, and only then, variables like corridor and state dimensionality can be set
        :return:
        """

        # set timelimit to multiplier specified in config * planned route total time
        route_duration = SimulationTimeConverter.duration_between(
            self.bus.route.origin.departure, self.bus.route.destination.departure
        )
        self._timelimit = (
            self._config.dynamic_routing_config.timelimit_multiplier * route_duration
        )

        # parse or create corridor
        if self._config.dynamic_routing_config.corridor is None:
            self._corridor = self._geodesic_env.corridor(
                self.bus.route.origin.get_hexagon_id(resolution=self._action_res),
                self.bus.route.destination.get_hexagon_id(resolution=self._action_res),
                k=2,
            )
        elif isinstance(self._config.dynamic_routing_config.corridor, set):
            self._corridor = self._config.dynamic_routing_config.corridor
        else:
            with open(self._config.dynamic_routing_config.corridor) as f:
                # also assign the parsed corridor back to the config for other reads of it
                self._corridor = self._config.dynamic_routing_config.corridor = (
                    ast.literal_eval(f.read())
                )

        self._corridor_dim = len(self._corridor)
        self._corridor_sorted = sorted(self._corridor)
        # position (vector of corridor size) + demands (matrix of corridor size^2) + remaining time
        self._state_size_flattened = (
            self._corridor_dim + self._corridor_dim * self._corridor_dim + 1
        )

        # let learning agent know
        self._initialized.succeed()

    def state(self):  # noqa: ANN201
        """
        We need:
        - Distance to terminal destination
        - Passengers [{distance to destination, remaining wait/walk}, ...]
        - Demands [{distance to origin, distance to destination, wait/walk}, ...]
        - Delay
        which represents the most complete picture of the environment/world the agent has at the moment
        """
        # S_t, as dict
        demands = self._get_viable_demands()

        # build OD matrix: m[start hex][end hex] = OD count for all currently known demands
        m = np.zeros((self._corridor_dim, self._corridor_dim), dtype=int)
        for d in demands:
            try:
                start = self._corridor_sorted.index(
                    d.origin.get_hexagon_id(self._action_res)
                )
                end = self._corridor_sorted.index(
                    d.destination.get_hexagon_id(self._action_res)
                )
                m[start][end] += 1
            except ValueError as e:
                logging.debug(
                    f"Bus update state: Encountered demand at edge of hexagon: {e}",  # noqa: G004
                    extra={"clazz": self.__class__.__name__, "oid": self._id},
                )
                # for now we are skipping it. I don't see a good way to solve the geometry inconsistency
                continue

        # also build "OD-demands" for each passenger in the bus:
        # origin = current position, destination = drop-off
        for p in self.bus._seats:  # noqa: SLF001
            try:
                start = self._corridor_sorted.index(
                    self.bus._position.get_hexagon_id(self._action_res)  # noqa: SLF001
                )
                end = self._corridor_sorted.index(
                    p.transport_task.destination.get_hexagon_id(self._action_res)
                )
                m[start][end] += 1
            except ValueError as e:
                # TODO: think about below
                # if a passenger is already in the bus, the edge case must be the destination
                # because the passenger can never be dropped of at the destination (with vicinity=hexagon)
                # this demand should be pruned before even becoming a passenger
                logging.debug(
                    f"Bus update state: Encountered passenger demand at edge of hexagon: {e}",  # noqa: G004
                    extra={"clazz": self.__class__.__name__, "oid": self._id},
                )
                # for now we are skipping it. I don't see a good way to solve the geometry inconsistency
                continue

        # build position vector v[hex] =1 if bus is at hex, else 0
        position = np.zeros(self._corridor_dim, dtype=int)
        pos = self._corridor_sorted.index(
            self.bus._position.get_hexagon_id(self._action_res)  # noqa: SLF001
        )
        position[pos] = 1

        # S_t, as numpy 3d matrix
        return self._state_to_numpy(
            {
                "position": position,
                "demands": m,
                "remaining_time": int(
                    self._timelimit - (self.env.now - self.bus._spawned)  # noqa: SLF001
                ),
            }
        )

    @staticmethod
    def _state_to_numpy(state: dict):  # noqa: ANN205
        # ndarray of corridor dim * corridor dim + corridor dim + 1
        # 1) OD demands (matrix) 2) agent position (one hot vector), 3) remaining driving time (scalar)
        return np.concatenate(
            (
                state["demands"].reshape(-1),
                state["position"],
                [state["remaining_time"]],
            ),
            dtype=int,
        )

    def _take_action(self, action: str | None = None):
        """
        Actions in hexagonal grid, stay is also allowed.

                     up
                     __
        up-left    /    \\  up-right
        down-left  \\ __ /  down-right
                    down

        """

        if action == "STAY":
            # even though the bus does not move, timeout for the average movement duration
            # otherwise the action does have no consequence, when another action immediately follows
            yield self.env.timeout(
                h3.average_hexagon_edge_length(
                    self._config.dynamic_routing_config.action_resolution,
                    unit="m",
                )
                / self.bus._velocity  # noqa: SLF001
            )
        else:
            hex_id = h3.latlng_to_cell(
                *self.bus.position.getExactLocation(),
                self._config.dynamic_routing_config.action_resolution,
            )
            new_hex = self.bus._geodesic_env.move_in_layer(hex_id, action)  # noqa: SLF001
            new_centroid = self.bus._geodesic_env.get_centroid(  # noqa: SLF001
                new_hex, f"hex_{self._config.dynamic_routing_config.action_resolution}"
            )

            new_position = GeodesicPosition(*new_centroid)

            distance = self.bus.position >> new_position
            self.bus._dist_traveled += (  # noqa: SLF001
                distance  # add to overall travel distance
            )
            duration = distance / self.bus._velocity  # in minutes  # noqa: SLF001

            self._state = VehicleState.EN_ROUTE_DETOUR

            yield self.env.timeout(duration)

            self.distance += distance
            self.duration += duration

            self.bus._update_positions(new_position)  # noqa: SLF001

            region_id = new_position.get_region_id(self._action_res)

            logging.debug(
                f"Current position {new_position} in region {region_id}.",  # noqa: G004
                extra={"clazz": self.__class__.__name__, "oid": f"Bus {self.bus._id}"},  # noqa: SLF001
            )

            if region_id == self.bus._route.destination.get_hexagon_id(  # noqa: SLF001
                self._action_res
            ):
                self.bus._state = VehicleState.AT_TERMINAL_DESTINATION  # noqa: SLF001
                logging.info(
                    f"Bus has arrived at its terminal destination at time {self.bus._time.now_as_str()}",  # noqa: G004, SLF001
                    extra={
                        "clazz": self.__class__.__name__,
                        "oid": f"Bus {self.bus._id}",  # noqa: SLF001
                    },
                )
                self.bus._has_reached_terminal.succeed()  # noqa: SLF001

    def reset(self):  # noqa: ANN201
        # not a reset function, strictly speaking as would be with a gym environment
        # rather this halts the simulation such that a new run can be started from the outer routine
        self._world.stop_all_processes()  # this stops demand generation

    def _test_action(self, action: str, evaluation: bool) -> bool:
        hex_id = h3.latlng_to_cell(
            *self.bus._position.getExactLocation(),  # noqa: SLF001
            self._action_res,
        )

        if action == "STAY":
            return True
        else:
            # check if hexagon is out of corridor - action is forbidden
            new_hex = self._geodesic_env.move_in_layer(hex_id, action)
            return True if new_hex in self._corridor else False

    def _get_reward(self):  # noqa: ANN202
        # yield self._action_taken
        # self._action_taken = self.env.event()  # only reset it after we have entered the method

        self._check_terminal()

        if self._unreachable_destination:
            logging.info(
                "Episode is cancelled, destination is unreachable within time limit",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            self.duration = None
            self.distance = None

        # reward is service level (1 drop off = +1 reward)
        reward = self.bus._dropoffs * self._config.dynamic_routing_config.reward  # noqa: SLF001
        if reward > 0:
            logging.debug(
                f"Service Level was increased by {reward!s}",  # noqa: G004
                extra={"clazz": self.__class__.__name__, "oid": self.bus._id},  # noqa: SLF001
            )

        if (
            self._reached_timelimit and not self.reached_destination
        ) or self._unreachable_destination:
            reward -= self._config.dynamic_routing_config.penalty

        # reset drop offs
        self.bus._dropoffs = 0  # noqa: SLF001

        return reward

    def _check_terminal(self):  # noqa: ANN202
        self.reached_destination = (
            True if self.bus.state is VehicleState.AT_TERMINAL_DESTINATION else False
        )
        self._reached_timelimit = (
            True if self.env.now - self.bus._spawned > self._timelimit else False  # noqa: SLF001
        )

        # TODO: this is still optimistic, bus needs to move between hexagons, not euclidean/haversine
        remaining_time = self._timelimit - (self.env.now - self.bus._spawned)  # noqa: SLF001
        timeto_destination = (
            self.bus.position >> self.bus.route.destination
        ) / self.bus._velocity  # noqa: SLF001
        self._unreachable_destination = (
            True if remaining_time < timeto_destination else False
        )
        # unreachable_destination = False # JUST FOR DEBUGGING

        terminal = (
            self._reached_timelimit
            or self.reached_destination
            or self._unreachable_destination
        )

        if terminal:
            return True
        else:
            return False

    def _get_viable_demands(self):  # noqa: ANN202
        users = self._tracking.list_tracked("TransitUser")
        transport_tasks = [self._tracking.get(x, "transport_task") for x in users]

        demands_in_corridor = self._geodesic_env.filter_demands_by_area(
            transport_tasks, self._corridor
        )
        demands_in_direction = self._geodesic_env.filter_demands_by_direction(
            demands_in_corridor, self.bus
        )

        return demands_in_direction
