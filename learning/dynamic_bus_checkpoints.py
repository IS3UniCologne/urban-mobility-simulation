import ast
import logging

import h3
import numpy as np
from h3.unstable import vect
from shapely.geometry import Polygon
from simpy import Environment

from learning.interface.learning_interface import LearningInterface
from learning.spaces.action_space import BadAction, ForbiddenAction
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import VehicleState
from simulation.helper.time import SimulationTimeConverter
from simulation.world.world import World
from tracking.tracking import Tracking


class DynamicBusCheckpointProblem(LearningInterface):
    """
    Class that implements the LearningInterface and bridges RL agents and the simulation
    The problem is as follows:

    A bus has to fulfill checkpoints on its route, that have time limits and can
    deviate from the pre-planned route only between these fixed checkpoints.
    A checkpoint is always a guaranteed drop-off for passengers.

    A routing corridor defines its routing area, its checkpoints and associated time limits.
    The terminal destination is also considered a "checkpoint" with a time limit.

    version 0.1
    """

    def __init__(self, env: Environment):
        super(DynamicBusCheckpointProblem, self).__init__(env)

        self._config = Configuration()
        self._problem_config = self._config.dynamic_checkpoint_routing_config

        # Environment / World state
        self._geodesic_env = GeodesicEnvironment.getInstance()
        self._world = World.instance()
        if self._problem_config.alignment_cache is not None:
            self._demands_in_corridor_cache = self._problem_config.alignment_cache
        else:
            self._demands_in_corridor_cache = {}
        if self._problem_config.alignment_cell_cache is not None:
            self._demands_in_cell_cache = self._problem_config.alignment_cell_cache
        else:
            self._demands_in_cell_cache = {}

        # H3 action resolution
        self._action_res = self._problem_config.action_resolution

        # Tracking
        self._tracking = Tracking.instance()

        # KPI
        self.reached_destination = False
        self.distance = 0
        self.duration = 0

        # inject bus, checkpoints, timelimits and corridor later, when spawned by operator
        self.bus = None
        self._checkpoints = None
        self._checkpoint_dim = None
        self._corridor = None
        self._corridor_dim = None
        self._corridor_sorted = None
        self._corridor_poly = None
        self._next_checkpoint = None
        self._timelimits = []

        # TODO: should the problem define the state space? Or should a StateSpace handle this?
        self._state_size_flattened = None

    def problem_init(self):
        # parse or create corridor
        if self._problem_config.corridor is None:
            self._corridor = self._geodesic_env.corridor(
                self.bus.route.origin.get_hexagon_id(resolution=self._action_res),
                self.bus.route.destination.get_hexagon_id(resolution=self._action_res),
                k=2,
            )
        elif isinstance(self._problem_config.corridor, set):
            self._corridor = self._problem_config.corridor
        else:
            with open(self._problem_config.corridor, "r") as f:
                # also assign the parsed corridor back to the config for other reads of it
                self._corridor = self._problem_config.corridor = ast.literal_eval(
                    f.read()
                )

        # parse or create checkpoints
        if isinstance(self._problem_config.checkpoints, int):
            # TODO: this yields GeodesicPoints not Stop IDs - this will break
            self._checkpoints = self._equidistant_checkpoints(
                n_checkpoints=self._problem_config.checkpoints
            )
        else:
            # also include the terminal destination stop id
            self._checkpoints = self._problem_config.checkpoints + [
                self.bus.route.destination.stop_id
            ]

        self._next_checkpoint = self._checkpoints[0]

        # update direction
        self._problem_config.direction = self._get_direction(
            self.bus.route.route_stop_by_id(self._next_checkpoint)
        )

        # set timelimits using the multiplier uniformly distributed over all checkpoints
        for c in self._checkpoints:
            # set timelimit from origin to a checkpoint to multiplier specified in config
            # * planned route total time from origin to that checkpoint
            # a PublicTransitRoute has stop_ids that start at origin=0
            route_duration = SimulationTimeConverter.duration_between(
                self.bus.route.origin.departure,
                self.bus.route.route_stop_by_id(c).departure,
            )
            self._timelimits.append(
                self._problem_config.timelimit_multiplier * route_duration
            )

        self._checkpoint_dim = len(self._checkpoints)
        self._corridor_dim = len(self._corridor)
        self._corridor_sorted = sorted(self._corridor)
        self._corridor_poly = Polygon(
            h3.h3_set_to_multi_polygon(self._corridor, geo_json=False)[0][0]
        )
        self._problem_config.area = self._corridor_poly
        # using this, initialize state size for agent
        # corridor_dim * 2 (position bus and demand origins)
        # + 2 * checkpoint_dim (checkpoint timelimits)
        # TODO: do we need more information?
        self._state_size_flattened = self._corridor_dim * 2 + self._checkpoint_dim * 2

        # let learning agent know
        self._initialized.succeed()

    def state(self):
        """
        We need:
        - Pick-up demands, aggregates per corridor cell
        - Current position bus within the corridor
        - Remaining checkpoints
        - Remaining time-limits of checkpoints
        """
        demands = self._get_viable_demands()

        # the first corridor_dim values are for the position
        # the second corridor_dim values are for the pick-up demands
        # the first checkpoint_dim values are for signaling the remaining checkpoints
        # the last values (checkpoint_dim) are for the remaining times of checkpoints
        x = np.zeros(self._state_size_flattened, dtype=np.float32)

        # build position vector v[hex] =1 if bus is at hex, else 0
        pos = self._corridor_sorted.index(
            self.bus.position.get_hexagon_id(self._action_res)
        )
        x[pos] = 1

        # build pick-up demand vector v[hex] = pick-up count for all currently known demands
        for d in demands:
            try:
                start = self._corridor_sorted.index(
                    d.origin.get_hexagon_id(self._action_res)
                )
                x[self._corridor_dim + start] += 1
            except ValueError as e:
                logging.debug(
                    f"Bus update state: Encountered demand at edge of hexagon: {e}",
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )
                # for now we are skipping it. I don't see a good way to solve the geometry inconsistency
                continue

        # scale demands to [0,1]
        x_demands = x[self._corridor_dim : self._corridor_dim * 2]
        x[self._corridor_dim : self._corridor_dim * 2] = (
            x_demands - x_demands.min()
        ) / (x_demands.max() - x_demands.min())

        # build "attention" vector v[checkpoint] = 1 if not reached yet
        # build timelimits vector v[checkpoint] = remaining time for all checkpoints incl terminal destination
        for i, c in enumerate(self._checkpoints, start=0):
            x[2 * self._corridor_dim + i] = 1 if c >= self._next_checkpoint else 0
            x[2 * self._corridor_dim + self._checkpoint_dim + i] = self._timelimits[
                i
            ] - (self.env.now - self.bus._spawned)

        # scale timelimits to [-1,1] but keep sign ([-1,1] only possible if min = max)
        # TODO: is this a good scaling method?
        x_timelimits = x[self._corridor_dim * 2 + self._checkpoint_dim :]
        x[self._corridor_dim * 2 + self._checkpoint_dim :] = (
            x_timelimits / abs(x_timelimits).max()
        )

        return x
        # return np.zeros(self._state_size_flattened, dtype=int)

    def reset(self):
        # not a reset function, strictly speaking as would be with a gym environment
        # rather this halts the simulation such that a new run can be started from the outer routine
        self._world.stop_all_processes()  # this stops demand generation and deregisters users

        # retain cache
        self._problem_config.alignment_cache = self._demands_in_corridor_cache

    def _check_terminal(self):
        self.reached_destination = (
            True if self.bus.state is VehicleState.AT_TERMINAL_DESTINATION else False
        )
        self._reached_timelimit = (
            True if self.env.now - self.bus._spawned > self._timelimits[-1] else False
        )

        remaining_time = self._timelimits[-1] - (self.env.now - self.bus._spawned)
        # the minimum time to destination is a "straight" h3 line times edge length (-1) divided by speed
        time_to_destination = (
            (
                len(
                    h3.h3_line(
                        self.bus.position.get_hexagon_id(),
                        self.bus.route.destination.get_hexagon_id(),
                    )
                )
                - 1
            )
            * h3.edge_length(self._action_res, unit="m")
            / self.bus._velocity
        )
        self._unreachable_destination = (
            True if remaining_time < time_to_destination else False
        )

        terminal = (
            self._reached_timelimit
            or self.reached_destination
            or self._unreachable_destination
        )

        if terminal:
            return True
        else:
            return False

    def _get_reward(self):
        self._check_terminal()

        # reward is service level (1 pick-up = +1 reward)
        reward = self.bus._pickups * self._problem_config.reward

        if reward > 0:
            logging.debug(
                f"Service Level was increased by {str(reward)}",
                extra={"clazz": self.__class__.__name__, "oid": self.bus._id},
            )

        if self._unreachable_destination:
            if self.reached_destination:
                pass
            logging.info(
                "Episode is cancelled, destination is unreachable within time limit",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            self.duration = None
            self.distance = None

        # penalize unreachable destination through time limit
        if (
            self._reached_timelimit and not self.reached_destination
        ) or self._unreachable_destination:
            reward -= self._problem_config.penalty_unreachable

        # penalize missed timelimit of next checkpoint (if missed), proportional to excess time
        # TODO: is this too harsh?
        reward += (
            min(
                0,
                (
                    self._timelimits[self._checkpoints.index(self._next_checkpoint)]
                    - (self.env.now - self.bus._spawned)
                ),
            )
            * self._problem_config.penalty_checkpoints
        )

        # TODO: penalize non-dropped of passengers?

        # reset drop offs and pickups
        self.bus._dropoffs = 0
        self.bus._pickups = 0

        return np.float32(reward)  # for tensors later on

    def _take_action(self, action):
        """
        Actions in hexagonal grid

                     up
                     __
        up-left    /    \\  up-right
        down-left  \\ __ /  down-right
                    down

        """
        hex_id = h3.geo_to_h3(
            *self.bus.position.getExactLocation(), resolution=self._action_res
        )
        new_hex = self.bus._geodesic_env.move_in_layer(hex_id, action)
        new_centroid = self.bus._geodesic_env.get_centroid(
            new_hex, f"hex_{self._action_res}"
        )

        new_position = GeodesicPosition(*new_centroid)

        distance = self.bus.position >> new_position
        self.bus._dist_traveled += distance  # add to overall travel distance
        duration = distance / self.bus._velocity  # in minutes

        self._state = VehicleState.EN_ROUTE_DETOUR

        yield self.env.timeout(duration)

        self.distance += distance
        self.duration += duration

        self.bus._update_positions(new_position)

        # region_id, _ = new_position.get_hexagon(self._action_res)

        if new_hex == self.bus.route.destination.get_hexagon_id(self._action_res):
            self.bus._state = VehicleState.AT_TERMINAL_DESTINATION
            logging.info(
                f"Bus has arrived at its terminal destination at time {self.bus._time.now_as_str()}",
                extra={"clazz": self.__class__.__name__, "oid": f"Bus {self.bus._id}"},
            )
            self.bus._has_reached_terminal.succeed()
            return

        if new_hex == self.bus.route.route_stop_by_id(
            self._next_checkpoint
        ).get_hexagon_id(self._action_res):
            self.bus._state = VehicleState.AT_STOP
            logging.info(
                f"Bus has arrived at the next checkpoint at time {self.bus._time.now_as_str()}",
                extra={"clazz": self.__class__.__name__, "oid": f"Bus {self.bus._id}"},
            )

            # advance checkpoint
            checkpoint_i = self._checkpoints.index(self._next_checkpoint)
            self._next_checkpoint = self._checkpoints[checkpoint_i + 1]

        # update direction
        self._problem_config.direction = self._get_direction(
            self.bus.route.route_stop_by_id(self._next_checkpoint)
        )

    def _test_action(self, action):
        """

        :param evaluation:
        :param action: the action to test
        :return: bool
        """
        hex_id = h3.geo_to_h3(
            *self.bus._position.getExactLocation(), resolution=self._action_res
        )

        # check if hexagon is out of corridor - action is forbidden
        new_hex = self._geodesic_env.move_in_layer(hex_id, action)
        incorridor = True if new_hex in self._corridor else False

        if not incorridor:
            raise ForbiddenAction

        # check if the direction of the action is target towards the next checkpoint
        allowed_direction = self._problem_config.direction
        lat, lng = h3.h3_to_geo(new_hex)
        projected_direction = self._get_direction(GeodesicPosition(lat, lng))
        indirection = self._geodesic_env.direction_aligns(
            projected_direction, allowed_direction
        )

        if not indirection:
            raise BadAction

    def _handle_bad_action(self, action):
        # # with 50/50 reject the bad action or execute it with penalty
        # reject = True if np.random.rand() <= .5 else False
        # if reject:
        #     return self._problem_config.penalty_goingback
        # else:
        #     raise ForbiddenAction
        return 0

    def _get_direction(self, destination: GeodesicPosition):
        return self._geodesic_env.get_bearing(
            *self.bus.position.getExactLocation(), *destination.getExactLocation()
        )

    def _get_viable_demands(self):
        users = self._tracking.list_tracked("TransitUser")
        transport_tasks = [self._tracking.get(x, "transport_task")[1] for x in users]

        demands_in_corridor = self._demands_in_corridor(transport_tasks)
        demands_in_direction = self._geodesic_env.filter_demands_by_direction(
            demands_in_corridor, self.bus
        )

        return demands_in_direction

    def _demands_in_corridor(self, transport_tasks):
        d = []
        task_keys = [
            (x.origin.getExactLocation(), x.destination.getExactLocation())
            for x in transport_tasks
        ]
        check_keys = []
        check_tasks = []

        for k, v in zip(task_keys, transport_tasks):
            try:
                d.append(v) if self._demands_in_corridor_cache[k] else None
            except KeyError:
                # if the cache does not have the demand itself, check later when checking cells
                check_keys.append(k), check_tasks.append(v)

        # use iterable is True if not empty
        if check_keys:
            # hint: geojson=False (default) is deliberate, as vect.geo_to_h3 expects (lat,lng)
            check_cells = list(
                zip(
                    *(
                        vect.geo_to_h3(
                            *zip(*[x.origin.getExactLocation() for x in check_tasks]),
                            res=self._action_res,
                        ),
                        vect.geo_to_h3(
                            *zip(
                                *[x.destination.getExactLocation() for x in check_tasks]
                            ),
                            res=self._action_res,
                        ),
                    )
                )
            )
            for i, k, v in zip(check_keys, check_cells, check_tasks):
                try:
                    d.append(v) if self._demands_in_cell_cache[k] else None
                except KeyError:
                    # if the cell cache does also not have the transport task,
                    # use computationally heavy geodesic env search

                    if self._geodesic_env.filter_demands_by_area(
                        [v], self._corridor_poly
                    ):
                        d.append(v)
                        self._demands_in_corridor_cache[i] = True
                        self._demands_in_cell_cache[k] = True
                    else:
                        self._demands_in_corridor_cache[i] = False
                        self._demands_in_cell_cache[k] = False

        return d

    def _equidistant_checkpoints(self, n_checkpoints):
        diff_od = self.bus.route.destination.difference(self.bus.route.origin)
        diff_per_n = tuple(x / (n_checkpoints + 1) for x in diff_od)

        c = []
        for c_i in range(n_checkpoints):
            c.append(
                GeodesicPosition(
                    *(
                        x + (c_i + 1) * y
                        for x, y in zip(
                            self.bus.route.origin.getExactLocation(), diff_per_n
                        )
                    )
                )
            )
        # also include the terminal destination (not included in the number of checkpoints)
        c.append(self.bus.route.destination)

        return c
