from abc import ABC, abstractmethod

from simulation.helper.configuration.configuration import Configuration


class RLAgent(ABC):
    def __init__(self):  # noqa: ANN204
        # Configuration
        self._config = Configuration()

        # Rewards
        self._reward = 0
        self._cumulative_reward = 0

    @property
    def reward(self):  # noqa: ANN201
        return self._reward

    @reward.setter
    def reward(self, reward):  # noqa: ANN001, ANN202
        self._reward = reward

    @property
    def cumulative_reward(self):  # noqa: ANN201
        return self._cumulative_reward

    @cumulative_reward.setter
    def cumulative_reward(self, cumulative_reward):  # noqa: ANN001, ANN202
        self._cumulative_reward = cumulative_reward

    @abstractmethod
    def learn(self):  # noqa: ANN201
        pass

    @abstractmethod
    def use(self):  # noqa: ANN201
        pass
