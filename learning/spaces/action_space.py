import numpy
from numpy.random import choice


class BadAction(Exception):
    pass


class ForbiddenAction(Exception):
    pass


class DiscreteActionSpace:
    def __init__(self, actions: list[str]):  # noqa: ANN204
        self._actions = actions

    @property
    def actions(self):  # noqa: ANN201
        return self._actions

    def num_choices(self):  # noqa: ANN201
        return len(self._actions)

    def index(self, action):  # noqa: ANN001, ANN201
        return self._actions.index(action)

    def action_as_binary_vector(self, action):  # noqa: ANN001, ANN201
        return numpy.array([1 if x == action else 0 for x in self._actions])

    def binary_vector_as_action(self, vector):  # noqa: ANN001, ANN201
        return self._actions[numpy.argmax(vector)]

    def sample_action_uniformly(self):  # noqa: ANN201
        return choice(self._actions)
