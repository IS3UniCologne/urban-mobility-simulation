from math import sqrt
import logging
from numpy.random import choice
import numpy as np

from simulation.agent.action_space import ActionSpace


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

    def __init__(self, state_dim, action_dim, init_values = None):
        if init_values is not None:
            assert state_dim * action_dim == len(init_values)
            self._weights = np.zeros(state_dim * action_dim) + init_values
        else:
            self._weights = np.zeros(state_dim * action_dim)

    def evaluate_value(self, state, action):
        s = state # vector [d_terminal_x, d_terminal_y]
        a = action # binary vector [1, 2, 3, 4, 5, 6]
        w = self._weights
        return eval(ValueFunctionApproximator.function)

    @staticmethod
    def evaluate_gradient(state, action):
        s = state # vector [d_terminal_x, d_terminal_y]
        a = action # binary vector [1, 2, 3, 4, 5, 6]
        return eval(ValueFunctionApproximator.gradient)

    @property
    def weights(self):
        return self._weights

    @weights.setter
    def weights(self, w):
        self._weights = w


def reward_bus(state, terminal = False):
    """

    This function maps bus states to rewards.

    :param state: env state as given by the bus agent
    :return: numerical reward +/- or none
    """

    if terminal:
        return 10
    else:
        # we oversimplify a lot here, coming from a geodesic environment, but we just wanna know a approximate absolute
        # distance measure for constructing the reward
        distance = sqrt(state['d_terminal'][0]**2 + state['d_terminal'][1]**2)

        return -distance


def vectorize_state(state):
    return np.array([state['d_terminal'][0], state['d_terminal'][1]])


def policy(state, q_hat, eps):
    actionspace = ActionSpace.instance()

    if np.random.rand() > eps:
        q_values = []
        for a in actionspace.actions:
            q_values.append(q_hat.evaluate_value(state, actionspace.action_as_binary_vector(a)))
        return actionspace.actions[argmax_rand(q_values)]
    else:
        return actionspace.sample_action_uniformly()


def argmax_rand(arr):
    # break ties randomly, np.argmax() always picks first max
    return np.random.choice(np.flatnonzero(arr == np.max(arr)))
