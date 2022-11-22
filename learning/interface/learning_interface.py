import logging
from abc import ABC, abstractmethod
import simpy

from learning.spaces.action_space import ActionForbidden


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
        self._step_executed = self.env.event()

    @property
    def initialized(self):
        return self._initialized

    @property
    def problem_config(self):
        return self._problem_config

    @property
    def state_size_flattened(self):
        return self._state_size_flattened

    def step(self, action):
        """
        This method directly interacts with the simulation, the expected behavior of receiving an action instruction
        must thus be implemented in the receiving agent in the simulation!

        :param action: A
        :return: S, R, T
        """
        if not self._test_action(action):
            logging.debug(f'Action {action} is forbidden, sampling again',
                          extra={"clazz": self.__class__.__name__, "oid": ""})
            raise ActionForbidden

        yield self.env.process(self._take_action(action))
        logging.debug(f'Agent takes action {action}',
                      extra={"clazz": self.__class__.__name__, "oid": ""})

        self._step_executed.succeed()
        self._step_executed = self.env.event()

        return self.state(), self._get_reward(), self._check_terminal()

    @abstractmethod
    def state(self):
        """
        This method requests the information necessary for constructing a problem-specific state from tracking
        The tracking capability must be implemented before you can request information!

        :return: vector or array representation of the observed environment, constricted to the problem-specific state S
        """
        pass

    @abstractmethod
    def _check_terminal(self):
        pass

    @abstractmethod
    def _get_reward(self):
        pass

    @abstractmethod
    def _take_action(self, action):
        pass

    @abstractmethod
    def _test_action(self, action):
        pass

