import numpy
from numpy.random import choice
from beartype import beartype
from typing import List, Any, Union, Optional, NoReturn


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
    @beartype
    def init(actions: List[Any], reset: bool = False) -> "ActionSpace":
        """Public constructor"""
        if ActionSpace.__instance is None or reset is True:
            ActionSpace(actions, reset)
        return ActionSpace.__instance

    @beartype
    def __init__(self, actions: List[Any], reset: bool = False) -> None:
        """Virtually private constructor."""
        if ActionSpace.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            ActionSpace.__instance = self
            super(ActionSpace, self).__init__()

        self._actions = actions

    @property
    def actions(self) -> List[Any]:
        return self._actions

    @beartype
    def dimensionality(self) -> int:
        return len(self._actions)

    @beartype
    def index(self, action: Any) -> int:
        return self._actions.index(action)

    @beartype
    def action_as_binary_vector(self, action: Any) -> numpy.ndarray:
        return numpy.array([1 if x == action else 0 for x in self._actions])

    @beartype
    def binary_vector_as_action(self, vector: numpy.ndarray) -> Any:
        return self._actions[numpy.argmax(vector)]

    @beartype
    def sample_action_uniformly(self) -> Any:
        return choice(self._actions)
