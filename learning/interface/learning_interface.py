from abc import ABC, abstractmethod
import simpy


class LearningInterface(ABC):
    """
    Interface for all problem-specific abstraction layers that bridge simulation and learning agent implementations
    """

    # TODO: ideally, the RL agent facing interface should be a gym-compatible API?

    def __init__(self, env: simpy.Environment):
        self.env = env
        self._problem_config = None
        self._state_size_flattened = None
        self._initialized = self.env.event()

    @property
    def initialized(self):
        return self._initialized

    @property
    def problem_config(self):
        return self._problem_config

    @property
    def state_size_flattened(self):
        return self._state_size_flattened

    @abstractmethod
    def state(self):
        """
        This method requests the information necessary for constructing a problem-specific state from tracking
        The tracking capability must be implemented before you can request information!

        :return: vector or array representation of the observed environment, constricted to the problem-specific state S
        """
        pass

    @abstractmethod
    def step(self, action):
        """
        This method directly interacts with the simulation, the expected behavior of receiving an action instruction
        must thus be implemented in the receiving agent in the simulation!

        :param action: A
        :return: S, R, T
        """
        pass
