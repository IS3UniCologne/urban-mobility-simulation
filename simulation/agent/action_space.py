import logging
from enum import Enum

import numpy
from numpy.random import choice


class ActionSpace:
    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> "ActionSpace":
        """Static access method."""
        if ActionSpace.__instance is None:
            raise Exception("ActionSpace was not initialized")
        else:
            return ActionSpace.__instance

    @staticmethod
    def init(actions: list, reset=False):
        """Public constructor"""
        if ActionSpace.__instance is None or reset is True:
            ActionSpace(actions, reset)
        return ActionSpace.__instance

    def __init__(self, actions: list, reset: bool = False):
        """Virtually private constructor."""
        if ActionSpace.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            ActionSpace.__instance = self
            super(ActionSpace, self).__init__()

        self._actions = actions

    @property
    def actions(self):
        return self._actions

    def dimensionality(self):
        return len(self._actions)

    def index(self, action):
        return self._actions.index(action)

    def action_as_binary_vector(self, action):
        return numpy.array([1 if x == action else 0 for x in self._actions])

    def binary_vector_as_action(self, vector):
        return self._actions[numpy.argmax(vector)]

    def sample_action_uniformly(self):
        return choice(self._actions)
