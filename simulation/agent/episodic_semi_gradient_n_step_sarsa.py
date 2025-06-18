import logging
from copy import deepcopy
from math import sqrt

import h3
import numpy as np
import simpy

from simulation.agent.episodic_semi_gradient_sarsa import ValueFunctionApproximator
from simulation.agent.policy import Policy
from simulation.agent.rl_agent import RLAgent
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleState


class EpisodicSemiGradientNStepSarsa(RLAgent):
    __slots__ = (
        "_G",
        "_actions",
        "_alpha",
        "_eps",
        "_gamma",
        "_n",
        "_q_hat",
        "_rewards",
        "_states",
    )

    def __init__(self, env: simpy.Environment, q_hat: ValueFunctionApproximator):  # noqa: ANN204
        super(EpisodicSemiGradientNStepSarsa, self).__init__(env)  # noqa: UP008

        # Configuration
        self._alpha = self._config.transit_agent_config.alpha
        self._gamma = self._config.transit_agent_config.gamma
        self._eps = self._config.transit_agent_config.eps
        self._n = self._config.transit_agent_config.n

        # Value function
        self._q_hat = q_hat

        # state, action, reward history for t = 0...T, indexed by t
        self._states = []
        self._actions = []
        self._rewards = [0]  # R_0 is undefined

        # n-step return
        self._G = 0

    def run(self, bus):  # noqa: ANN001, ANN201
        s0 = deepcopy(bus._env_state)  # noqa: SLF001
        self._states.append(s0)
        self._decide_next_action(bus, s0)

        t = 0
        T = np.inf
        tau = -np.inf

        while True:
            if t < T:
                self._env.process(
                    bus._update_reward(self._states[t])  # noqa: SLF001
                )  # S_t
                yield self._env.process(self._take_action(bus, self._actions[t]))  # A_t
                self._rewards.append(self._reward)  # R_t+1
                self._states.append(deepcopy(bus._env_state))  # S_t+1  # noqa: SLF001
                if bus.state is VehicleState.AT_TERMINAL_DESTINATION:
                    T = t + 1
                else:
                    self._decide_next_action(bus, self._states[t + 1])  # A_t+1
            tau = t - self._n + 1
            if tau >= 0:
                self._G = sum(
                    self._gamma ** (i - tau - 1) * self._rewards[i]
                    for i in range(tau + 1, min(tau + self._n, T) + 1)
                )

                if tau + self._n < T:
                    s_tpn = self._vectorize_state(self._states[tau + self._n])
                    a_tpn = self._action_space.action_as_binary_vector(
                        self._actions[tau + self._n]
                    )
                    self._G += self._gamma**self._n * self._q_hat.evaluate_value(
                        s_tpn, a_tpn
                    )

                s_tau = self._vectorize_state(self._states[tau])
                a_tau = self._action_space.action_as_binary_vector(self._actions[tau])
                self._update_policy(s_tau, a_tau)

            t += 1
            if tau == T - 1:
                break

    def _decide_next_action(self, bus, state):  # noqa: ANN001, ANN202
        while True:
            a = Policy.decide(self._vectorize_state(state), self._q_hat, self._eps)
            try:
                bus.test_action(a)
            except NotImplementedError:
                # hexagon is out of layer bounding box - action is forbidden
                logging.debug(
                    f"Action {a} is forbidden, sampling again",  # noqa: G004
                    extra={"clazz": self.__class__.__name__, "oid": bus.id},
                )
                continue
            break

        logging.debug(
            f"Bus takes action {a}",  # noqa: G004
            extra={"clazz": self.__class__.__name__, "oid": bus.id},
        )

        self._actions.append(a)

    def _take_action(self, bus, action=None) -> simpy.events.Event:
        """
        Actions in hexagonal grid, stay is also allowed.

                     up
                     __
        up-left    /    \\  up-right
        down-left  \\ __ /  down-right
                    down

        """

        if action == "STAY":
            yield self._env.timeout(0.01)
        else:
            hex_id = h3.latlng_to_cell(
                *bus.position.getExactLocation(),
                self._config.transit_agent_config.action_resolution,
            )
            new_hex = bus._geodesic_env.move_in_layer(hex_id, action)  # noqa: SLF001
            new_centroid = bus._geodesic_env.get_centroid(  # noqa: SLF001
                new_hex, f"hex_{self._config.transit_agent_config.action_resolution}"
            )

            new_position = GeodesicPosition(*new_centroid)

            distance = bus.position >> new_position
            duration = distance / bus._velocity  # in minutes  # noqa: SLF001

            self._state = VehicleState.EN_ROUTE_DETOUR

            yield self._env.timeout(duration)

            bus._update_positions(new_position)  # noqa: SLF001

        bus._action_taken.succeed(action)  # noqa: SLF001
        bus._action_taken = self._env.event()  # noqa: SLF001

        return action

    def _update_policy(self, s, a):  # noqa: ANN001, ANN202
        # update weights based on semi gradient n-step sarsa

        self._q_hat.weights = self._q_hat.weights + self._alpha * (
            self._G - self._q_hat.evaluate_value(s, a)
        ) * self._q_hat.evaluate_gradient(s, a)

    @staticmethod
    def reward_state(state, terminal=False):  # noqa: ANN001, ANN205
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
            distance = sqrt(state["d_terminal"][0] ** 2 + state["d_terminal"][1] ** 2)

            return -distance

    @staticmethod
    def _vectorize_state(state):  # noqa: ANN001, ANN205
        return np.array([state["d_terminal"][0], state["d_terminal"][1]])
