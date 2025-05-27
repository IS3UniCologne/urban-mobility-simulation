from abc import ABC, abstractmethod

import simpy

from simulation.agent.action_space import ActionSpace
from simulation.agent.agent import Agent
from simulation.helper.configuration.configuration import Configuration


class RLAgent(ABC):
    __slots___ = ("_env", "_config", "_action_space", "_reward", "_reward_sum")

    def __init__(self, env: simpy.Environment):  # noqa: ANN204
        # Simulation Environment
        self._env = env

        # Configuration
        self._config = Configuration()

        # Action space
        self._action_space = ActionSpace.instance()

        # Rewards
        self._reward = 0
        self._reward_sum = 0

    @property
    def reward(self):  # noqa: ANN201
        return self._reward

    @reward.setter
    def reward(self, reward):  # noqa: ANN001, ANN202
        self._reward = reward

    @property
    def reward_sum(self):  # noqa: ANN201
        return self._reward_sum

    @reward_sum.setter
    def reward_sum(self, reward_sum):  # noqa: ANN001, ANN202
        self._reward_sum = reward_sum

    @abstractmethod
    def run(self, target: Agent):  # noqa: ANN201
        pass
