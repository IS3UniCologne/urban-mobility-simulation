import numpy
from numpy.random import choice
from typing import Any


class ActionSpace:
    # There is only one instance of this class.
    __instance = None

    __slots__ = ("_actions",) 

    @staticmethod
    def instance() -> "ActionSpace":
        """Static access method."""
        if ActionSpace.__instance is None:
            raise Exception("ActionSpace was not initialized")
        else:
            return ActionSpace.__instance

    @staticmethod
    
    def init(actions: list[Any], reset: bool = False) -> "ActionSpace":
        """Public constructor"""
        if ActionSpace.__instance is None or reset is True:
            ActionSpace(actions, reset)
        return ActionSpace.__instance

    
    def __init__(self, actions: list[Any], reset: bool = False) -> None:
        """Virtually private constructor."""
        if ActionSpace.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            ActionSpace.__instance = self
            super(ActionSpace, self).__init__()  # noqa: UP008

        self._actions = actions

    @property
    def actions(self) -> list[Any]:
        return self._actions

    
    def dimensionality(self) -> int:
        return len(self._actions)

    
    def index(self, action: Any) -> int: # noqa: ANN401
        return self._actions.index(action)

    
    def action_as_binary_vector(self, action:Any) -> numpy.ndarray: # noqa: ANN401
        return numpy.array([1 if x == action else 0 for x in self._actions])

    
    def binary_vector_as_action(self, vector: numpy.ndarray):  # noqa: ANN201
        return self._actions[numpy.argmax(vector)]

    
    def sample_action_uniformly(self):  # noqa: ANN201
        return choice(self._actions)
