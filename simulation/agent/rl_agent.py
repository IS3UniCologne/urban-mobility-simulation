from abc import ABC, abstractmethod

import simpy

from simulation.agent.action_space import ActionSpace
from simulation.agent.agent import Agent
from simulation.helper.configuration.configuration import Configuration


class RLAgent(ABC):
    def __init__(self, env: simpy.Environment):
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
    def reward(self):
        return self._reward

    @reward.setter
    def reward(self, reward):
        self._reward = reward

    @property
    def reward_sum(self):
        return self._reward_sum

    @reward_sum.setter
    def reward_sum(self, reward_sum):
        self._reward_sum = reward_sum

    @abstractmethod
    def run(self, target: Agent):
        pass
