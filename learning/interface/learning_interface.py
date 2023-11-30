import logging
from abc import ABC, abstractmethod

import numpy as np
import simpy

from learning.spaces.action_space import BadAction, ForbiddenAction


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

    def step(self, action, evaluation=False):
        """
        This method directly interacts with the simulation, the expected behavior of receiving an action instruction
        must thus be implemented in the receiving agent in the simulation!

        :param action: A
        :param evaluation: if set to true, test action is more lenient with raising ActionForbidden, problem-dependent
        :return: S, R, T
        """

        bad_action_penalty = 0

        try:
            self._test_action(action)
        except (BadAction, ForbiddenAction) as e:
            if evaluation and isinstance(e, BadAction):
                logging.debug(f'Action {action} is considered bad, but allowed in evaluation',
                              extra={"clazz": self.__class__.__name__, "oid": ""})
                pass
            elif not evaluation and isinstance(e, BadAction):
                logging.debug(f'Action {action} is considered bad, delegate decision',
                              extra={"clazz": self.__class__.__name__, "oid": ""})
                try:
                    bad_action_penalty = self._handle_bad_action(action)
                except ForbiddenAction as e:
                    # action was rejected, now considered forbidden
                    raise e from None
            else:
                # isinstance(e, ForbiddenAction) is True
                raise

        yield self.env.process(self._take_action(action))
        logging.debug(f'Agent takes action {action}',
                      extra={"clazz": self.__class__.__name__, "oid": ""})

        self._step_executed.succeed()
        self._step_executed = self.env.event()

        return self.state(), self._get_reward()-np.float32(bad_action_penalty), self._check_terminal()

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

    @abstractmethod
    def _handle_bad_action(self, action):
        """
        Problem-specific method to handle an action that is considered bad but is not forbidden
        Might raise ForbiddenAction, if the action is not executed
        Might return a penalty for executing the bad action

        :param action: The action to take, subject to problem-implementation
        :return: penalty for the bad action
        """
        pass

    @abstractmethod
    def reset(self):
        """
        In its current form, tell the simulation that the episode is finished, i.e. halt it
        TODO: gym-compatible?

        :return:
        """
        pass

