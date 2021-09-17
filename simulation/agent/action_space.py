import logging
from enum import Enum

from numpy.random import choice


class ActionSpace:
    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> 'ActionSpace':
        """ Static access method. """
        if ActionSpace.__instance is None:
            raise Exception("ActionSpace was not initialized")
        else:
            return ActionSpace.__instance

    @staticmethod
    def init(actions, probabilities = None):
        """ Static access method. """
        if ActionSpace.__instance is None:
            ActionSpace(actions, probabilities)
        return ActionSpace.__instance

    def __init__(self, actions, probabilities):
        """ Virtually private constructor. """
        if ActionSpace.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            ActionSpace.__instance = self
            super(ActionSpace, self).__init__()

        self._actions = actions
        self._probabilities = probabilities

    @property
    def actions(self):
        return self._actions

    @property
    def probabilities(self):
        return self._probabilities

    @probabilities.setter
    def probabilities(self, probabilities):
        self._probabilities = probabilities

    def sample_action(self):
        if self._probabilities is not None:
            return choice(self._actions, p=self._probabilities)
        else:
            logging.debug(f'No action probabilities are given, sampling from uniform probability distribution')
            self.sample_action_uniformly()

    def sample_action_uniformly(self):
        return choice(self._actions)
