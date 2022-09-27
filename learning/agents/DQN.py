import logging
from collections import deque
from copy import deepcopy
import numpy as np
import random
import tensorflow as tf
from keras import layers
from keras.losses import Huber
from keras.models import Sequential
from keras.optimizers import Adam
from keras.optimizers.schedules.learning_rate_schedule import ExponentialDecay

from learning.interface.learning_interface import LearningInterface
from learning.helper.policy import Policy
from learning.agents.rl_agent import RLAgent
from learning.spaces.action_space import ActionForbidden


class DQN(RLAgent):
    def __init__(self, problem: LearningInterface):
        super(DQN, self).__init__()

        self.problem = problem
        self._problem_config = self.problem.problem_config

        # Configuration
        self._action_space = self._problem_config.action_space
        self._alpha = self._config.DQN_config.alpha
        self._total_episodes = self._config.DQN_config.episodes
        self._episode = self._config.DQN_config.episode  # starting from 1
        if self._config.DQN_config.evaluation:
            self._eps = self._eps_min = 0
        else:
            self._eps_min = self._config.DQN_config.eps_min
            self._eps = self._config.DQN_config.eps
        self._eps_decay_strategy = self._config.DQN_config.eps_decay_strategy
        self._eps_decay = self._config.DQN_config.eps_decay
        self._eps_min = self._config.DQN_config.eps_min
        self._gamma = self._config.DQN_config.gamma
        self._penalty = self._problem_config.penalty
        self._reward = self._problem_config.reward
        self._replaybuffer_size = self._config.DQN_config.replaybuffer_size  # size in episodes
        # Experience Replay
        if self._config.DQN_config.replaybuffer is not None:
            if isinstance(self._config.DQN_config.replaybuffer, deque):
                self._replaybuffer = self._config.DQN_config.replaybuffer
            else:
                # use list as long as buffer size is not reached, then use deque
                if self._episode <= self._replaybuffer_size:
                    self._replaybuffer = self._config.DQN_config.replaybuffer
                else:
                    self._replaybuffer = deque(self._config.DQN_config.replaybuffer,
                                               maxlen=len(self._config.DQN_config.replaybuffer))
        else:
            self._replaybuffer = []
        self._min_experience = self._config.DQN_config.min_experience  # episodes in replay buffer before training starts
        self._use_double_q = self._config.DQN_config.double_q  # usage of Double Q Learning (Hasselt 2016)
        self._minibatch_size = self._config.DQN_config.batchsize  # training minibatch size
        self._target_net_update_threshold = self._config.DQN_config.target_update_threshold  # training steps before q net weights are propagated to target q net
        self._tau = self._config.DQN_config.tau
        self._learning_rate = None
        self._learning_rate_decay_steps = self._config.DQN_config.lr_decay_steps

        # tuple of dim (1, n hidden layers+1 for input layer),
        # output layer is fixed to n actions
        self._q_net_layer = self._config.DQN_config.q_net_layer

        # decay exponentially from initial_learning_rate to initial_learning_rate * decay_rate over decay_steps steps
        # lr = initial_learning_rate * decay_rate ^ (step / decay_steps)
        if self._config.DQN_config.lr_decay:
            self._learning_rate = ExponentialDecay(
                initial_learning_rate=0.01,
                decay_steps=self._learning_rate_decay_steps,
                decay_rate=0.1
            )
        else:
            self._learning_rate = 0.001  # adam default learning rate

        if self._config.DQN_config.optimizer is None:
            self._optimizer = Adam(learning_rate=self._learning_rate)
        else:
            self._optimizer = self._config.DQN_config.optimizer

        self._tensorboard = self._config.DQN_config.tensorboard

        # Random Number Generator
        # TODO: seed?
        self._random = np.random.default_rng()

        # defer model creation until the problem has initialized properly
        # this is important for problems where e.g. the state dimensions change depending on the problem instance
        self._q_net = None
        self._target_q_net = None
        self.problem.env.process(self._delayed_init())

    def _delayed_init(self):
        yield self.problem.initialized

        # Neural Nets
        self._q_net = self._create_model()
        self._target_q_net = self._create_model()
        if self._config.DQN_config.weights is not None:
            if type(self._config.DQN_config.weights) is str:
                # filepath is given
                logging.info(f'Loading weights from {self._config.DQN_config.weights} ...',
                             extra={"clazz": self.__class__.__name__, "oid": ""})
                self._q_net.load_weights(self._config.DQN_config.weights)
                self._target_q_net.load_weights(self._config.DQN_config.weights)
            else:
                # weights array from previous episode is given
                eval_weights, target_weights = self._config.DQN_config.weights
                self._q_net.set_weights(eval_weights)
                self._target_q_net.set_weights(target_weights)
        else:
            logging.debug(self._q_net.summary())
            logging.debug("Model Summary:",
                          extra={"clazz": self.__class__.__name__, "oid": ""})

            # in the first episode, initialize target q net weights = q net weights
            self._target_q_net.set_weights(self._q_net.get_weights())

    def _create_model(self):
        model = Sequential()

        input_layer_size = self.problem.state_size_flattened

        # Input
        model.add(layers.Dense(self._q_net_layer[0], input_dim=input_layer_size,
                               activation='tanh', kernel_initializer='glorot_uniform'))

        # Hidden Layers
        for layernodes in self._q_net_layer[1:]:
            model.add(layers.Dense(layernodes, activation='tanh', kernel_initializer='glorot_uniform'))

        # Output
        model.add(layers.Dense(self._action_space.num_choices(), activation='linear'))
        # model.compile(loss=tf.keras.losses.Huber(), optimizer='sgd', metrics=['accuracy'])
        model.compile(loss=Huber(), optimizer=self._optimizer, metrics=['accuracy'])

        return model

    def run(self):
        if self._config.DQN_config.evaluation:
            yield self.problem.env.process(self.use())
        else:
            yield self.problem.env.process(self.learn())

    def use(self):
        # Deep Q Learning with Experience Replay as in mnih2013 (deepmind atari paper)
        while True:
            state = deepcopy(self.problem.state())  # S_t, as dict
            action = self.policy(state)  # A_t, string such as "DOWN"
            try:
                _, reward, finished = yield self.problem.env.process(self.problem.step(action))
            except ActionForbidden:
                continue
            if finished:
                break

    def learn(self):

        # Deep Q Learning with Experience Replay as in mnih2013 (deepmind atari paper)
        while True:

            state = deepcopy(self.problem.state()) # S_t, as numpy 3d matrix
            action = self.policy(state)  # A_t, string such as "DOWN"
            action_index = self._action_space.index(action)  # A_t, index of action in action space

            try:
                next_state, reward, finished = yield self.problem.env.process(self.problem.step(action))
            except ActionForbidden:
                continue

            self._cumulative_reward += reward
            logging.debug(f'Current reward: {reward}, overall reward: {self._cumulative_reward}',
                          extra={"clazz": self.__class__.__name__, "oid": ""})

            self._replaybuffer.append((state, action_index, reward, next_state, finished))
            self._train(finished)

            if finished:
                if self._eps_decay_strategy != 'none':
                    # decay epsilon at end of episode
                    if self._eps > self._eps_min:
                        if self._eps_decay_strategy == 'exp':
                            # actually a power law function decay
                            self._eps *= self._eps_decay
                        elif self._eps_decay_strategy == 'linear':
                            # decay linearly from 1 to 0 over all episodes
                            self._eps = 1 - (1 / self._total_episodes) * self._episode
                        self._eps = max(self._eps_min, self._eps)
                break

        # retain decayed epsilon
        self._config.DQN_config.eps = self._eps
        logging.debug(f'Saving decayed epsilon into config: {str(self._eps)}',
                      extra={"clazz": self.__class__.__name__, "oid": f'Episode {self._episode}'})

        # retain optimizer steps for decayed learning rate
        self._config.DQN_config.optimizer = self._optimizer
        if self._config.DQN_config.lr_decay:
            logging.debug(
                f'Saving decayed learning rate into config: {str(self._learning_rate(self._optimizer.iterations))}',
                extra={"clazz": self.__class__.__name__, "oid": f'Episode {self._episode}'})

        # retain replaybuffer
        self._config.DQN_config.replaybuffer = self._replaybuffer
        logging.debug(f'Saving replay buffer into config. Size: {str(len(self._replaybuffer))}',
                      extra={"clazz": self.__class__.__name__, "oid": f'Episode {self._episode}'})

        # retain weights
        self._config.DQN_config.weights = (self._q_net.get_weights(), self._target_q_net.get_weights())
        logging.debug(f'Saving model weights into config.',
                      extra={"clazz": self.__class__.__name__, "oid": f'Episode {self._episode}'})

        self.problem.reset()

    def policy(self, state):
        rand = True if np.random.rand() <= self._eps else False

        if not rand:
            q_values = self._target_predict(tf.expand_dims(state, axis=0))
            # TODO: normalize / probabilities instead of argmax?
            max_q = Policy.argmax_rand(q_values)
            a = self._action_space.actions[max_q]
        else:
            a = self._action_space.sample_action_uniformly()

        return a

    def _train(self, terminal_state: bool):
        if self._episode >= self._min_experience:
            minibatch = random.sample(self._replaybuffer, self._minibatch_size)
            # minibatch = self._random.choice(self._replay_buffer, self._minibatch_size, replace=False)

            states_t = np.array([transition[0] for transition in minibatch])  # s0
            q_values_t = self._eval_predict(states_t).numpy()

            states_tp1 = np.array([transition[3] for transition in minibatch])  # s1

            if self._use_double_q:
                # Double Q-learning
                q_values_tp1 = self._eval_predict(states_tp1).numpy()
                q_values_tp1_t = self._target_predict(states_tp1).numpy()
            else:
                # Vanilla DQN with target network
                q_values_tp1 = self._target_predict(states_tp1).numpy()

            X = []
            y = []

            for i, (s0, a, r, s1, terminal) in enumerate(minibatch):
                if terminal:
                    target_q = r
                else:
                    if self._use_double_q:
                        target_q = r + self._gamma * q_values_tp1_t[i][
                            tf.math.argmax(q_values_tp1[i])]  # double Q-learning
                    else:
                        target_q = r + self._gamma * tf.math.reduce_max(
                            q_values_tp1[i])  # vanilla DQN with target network

                q_values = q_values_t[i]
                q_values[a] = target_q

                X.append(s0)
                y.append(q_values)

            self._q_net.fit(np.array(X), np.array(y), batch_size=self._minibatch_size, verbose=0, shuffle=False,
                            callbacks=[self._tensorboard] if terminal_state else None)

            if self._optimizer.iterations % self._target_net_update_threshold == 0:
                if self._tau is not None:
                    # do soft updates
                    theta = self._q_net.get_weights()
                    target_theta = self._target_q_net.get_weights()
                    for i, (w, w_t) in enumerate(zip(theta, target_theta)):
                        w_t = w * self._tau + w_t * (1 - self._tau)
                        assert len(target_theta[i]) == len(w_t)
                        target_theta[i] = w_t
                    assert len(target_theta) == len(self._target_q_net.get_weights())
                    self._target_q_net.set_weights(target_theta)
                else:
                    # do hard updates
                    self._target_q_net.set_weights(self._q_net.get_weights())

    @tf.function
    def _target_predict(self, state):
        try:
            return self._target_q_net(state, training=False)
        except Exception as e:
            pass

    @tf.function
    def _eval_predict(self, state):
        return self._q_net(state, training=False)
