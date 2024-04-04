from abc import ABC, abstractmethod


from simulation.helper.configuration.configuration import Configuration


class RLAgent(ABC):
    def __init__(self):
        # Configuration
        self._config = Configuration.instance()

        # Rewards
        self._reward = 0
        self._cumulative_reward = 0

    @property
    def reward(self):
        return self._reward

    @reward.setter
    def reward(self, reward):
        self._reward = reward

    @property
    def cumulative_reward(self):
        return self._cumulative_reward

    @cumulative_reward.setter
    def cumulative_reward(self, cumulative_reward):
        self._cumulative_reward = cumulative_reward

    @abstractmethod
    def learn(self):
        pass

    @abstractmethod
    def use(self):
        pass
