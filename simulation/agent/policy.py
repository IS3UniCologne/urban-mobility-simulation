import numpy as np

from simulation.agent.action_space import ActionSpace


class Policy:
    # TODO: currently this class is tailored for action-value functions, generalize
    def __init__(self):
        pass

    @staticmethod
    def argmax_rand(arr):
        """
        :param arr: Vector of (State-/Action-)Value Function Values
        :return: Index of max value in arr, with ties broken randomly
        """
        # break ties randomly, np.argmax() always picks first max
        try:
            return np.random.choice(np.flatnonzero(arr == np.max(arr)))
        except ValueError:
            raise Exception("possible NaNs in NN encountered")
    @classmethod
    def decide(cls, state, q_hat, eps):
        """

        :param state: State as n-dim (numpy) vector
        :param q_hat: ValueFunctionApproximator object that has a function and gradient that work with n-dim state vectors
        :param eps: epsilon for e-greedy action selection (0 = true on-policy, 1 = sample uniformly from action space)
        :return:
        """
        actionspace = ActionSpace.instance()

        if np.random.rand() > eps:
            q_values = []
            for a in actionspace.actions:
                q_values.append(q_hat.evaluate_value(state, actionspace.action_as_binary_vector(a)))
            return actionspace.actions[cls.argmax_rand(q_values)]
        else:
            return actionspace.sample_action_uniformly()
