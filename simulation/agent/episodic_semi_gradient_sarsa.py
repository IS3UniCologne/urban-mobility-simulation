import logging
from copy import deepcopy
from math import sqrt

import h3
import numpy as np
import simpy

from simulation.agent.action_space import ActionSpace
from simulation.agent.policy import Policy
from simulation.agent.rl_agent import RLAgent
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.vehicle.public_transit_bus import BusState


class ValueFunctionApproximator:
    # this function only looks at (d_terminal_x, d_terminal_y)
    function = "w[0] * s[0] * a[0] + w[1] * s[1] * a[0] + " \
               "w[2] * s[0] * a[1] + w[3] * s[1] * a[1] + " \
               "w[4] * s[0] * a[2] + w[5] * s[1] * a[2] + " \
               "w[6] * s[0] * a[3] + w[7] * s[1] * a[3] + " \
               "w[8] * s[0] * a[4] + w[9] * s[1] * a[4] + " \
               "w[10] * s[0] * a[5] + w[11] * s[1] * a[5] + " \
               "w[12] * s[0] * a[6] + w[13] * s[1] * a[6]"

    gradient = "np.array([" \
               "s[0] * a[0], " \
               "s[1] * a[0], " \
               "s[0] * a[1], " \
               "s[1] * a[1], " \
               "s[0] * a[2], " \
               "s[1] * a[2], " \
               "s[0] * a[3], " \
               "s[1] * a[3], " \
               "s[0] * a[4], " \
               "s[1] * a[4], " \
               "s[0] * a[5], " \
               "s[1] * a[5], " \
               "s[0] * a[6], " \
               "s[1] * a[6]" \
               "])"

    def __init__(self, state_dim, action_dim, init_values=None):
        if init_values is not None:
            assert state_dim * action_dim == len(init_values)
            self._weights = np.zeros(state_dim * action_dim) + init_values
        else:
            self._weights = np.zeros(state_dim * action_dim)

    def evaluate_value(self, state, action):
        s = state  # vector [d_terminal_x, d_terminal_y]
        a = action  # binary vector [1, 2, 3, 4, 5, 6]
        w = self._weights
        return eval(ValueFunctionApproximator.function)

    @staticmethod
    def evaluate_gradient(state, action):
        s = state  # vector [d_terminal_x, d_terminal_y]
        a = action  # binary vector [1, 2, 3, 4, 5, 6]
        return eval(ValueFunctionApproximator.gradient)

    @property
    def weights(self):
        return self._weights

    @weights.setter
    def weights(self, w):
        self._weights = w


class EpisodicSemiGradientSarsa(RLAgent):
    def __init__(self, env: simpy.Environment, q_hat: ValueFunctionApproximator):
        super(EpisodicSemiGradientSarsa, self).__init__(env)

        # Configuration
        self._alpha = self._config.transit_agent_config.alpha
        self._gamma = self._config.transit_agent_config.gamma
        self._eps = self._config.transit_agent_config.eps

        # Value function
        self._q_hat = q_hat

    def run(self, bus):
        while not bus.state == BusState.AT_TERMINAL_DESTINATION:
            # to get a value copy of a state we need to deepcopy, otherwise modifying self._env_state results in
            # modifying the "copy" which really is just a reference
            before_state = deepcopy(bus._env_state)
            self._env.process(bus._update_reward(before_state))
            action = yield self._env.process(self._take_action(bus))

            s = self._vectorize_state(before_state)
            s_ = self._vectorize_state(bus._env_state)
            a = self._action_space.action_as_binary_vector(action)
            if bus.state is BusState.AT_TERMINAL_DESTINATION:
                # update weights
                self._update_policy(s, a, terminal=True)
                # and go to next episode
                break

            a_ = self._action_space.action_as_binary_vector(Policy.decide(s_, self._q_hat, self._eps))

            # update weights
            self._update_policy(s, a, s_, a_)

        # clean up processes
        bus._state_update_process.interrupt()

        # and let the operator know
        bus._has_reached_terminal.succeed()

    def _take_action(self, bus):
        """
        Actions in hexagonal grid, stay is also allowed.

                     up
                     __
        up-left    /    \  up-right
        down-left  \ __ /  down-right
                    down

        """

        new_centroid = None

        while True:
            action = Policy.decide(self._vectorize_state(bus._env_state), self._q_hat, self._eps)

            if action == 'STAY':
                break
            else:
                try:
                    new_centroid = bus.test_action(action)
                except NotImplementedError:
                    # hexagon is out of layer bounding box - action is forbidden
                    logging.debug(f'Action {action} is forbidden, sampling again',
                                  extra={"clazz": self.__class__.__name__, "oid": bus.id})
                    continue
                break

        logging.debug(f'Bus takes action {action}',
                      extra={"clazz": self.__class__.__name__, "oid": bus.id})

        if new_centroid is None:
            yield self._env.timeout(.01)
        else:
            new_position = GeodesicPosition(*new_centroid)

            distance = bus.position >> new_position
            duration = distance / bus._velocity  # in minutes

            self._state = BusState.EN_ROUTE_DETOUR

            yield self._env.timeout(duration)

            bus._update_positions(new_position)

        bus._action_taken.succeed(action)
        bus._action_taken = self._env.event()

        return action

    def _update_policy(self, s, a, s_=None, a_=None, terminal=False):
        # update weights based on semi gradient sarsa

        if terminal:
            self._q_hat.weights = self._q_hat.weights + self._alpha * \
                                  (self._reward - self._q_hat.evaluate_value(s, a)) * \
                                  self._q_hat.evaluate_gradient(s, a)
        else:
            self._q_hat.weights = self._q_hat.weights + \
                                  self._alpha * (self._reward + self._gamma * self._q_hat.evaluate_value(s_, a_) -
                                                 self._q_hat.evaluate_value(s, a)) * self._q_hat.evaluate_gradient(s, a)

    @staticmethod
    def reward_state(state, terminal=False):
        """

        This function maps bus states to rewards.

        :param state: env state as given by the bus agent
        :param terminal: bool, is the state a terminal one?
        :return: numerical reward +/- or 0
        """

        if terminal:
            return 10
        else:
            # we oversimplify a lot here, coming from a geodesic environment, but we just wanna know a approximate absolute
            # distance measure for constructing the reward
            distance = sqrt(state['d_terminal'][0] ** 2 + state['d_terminal'][1] ** 2)

            return -distance

    @staticmethod
    def _vectorize_state(state):
        return np.array([state['d_terminal'][0], state['d_terminal'][1]])
