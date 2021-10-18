import logging
import os
from collections import deque
from copy import deepcopy

import h3
import numpy as np
import random
import simpy
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from keras.callbacks import TensorBoard
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.losses import Huber

from simulation.agent.action_space import ActionSpace
from simulation.agent.policy import Policy
from simulation.agent.rl_agent import RLAgent
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.vehicle.public_transit_bus import BusState, Bus

from line_profiler_pycharm import profile


class ModifiedTensorBoard(TensorBoard):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.step = 1
        self.writer = tf.summary.create_file_writer(self.log_dir)
        self._log_write_dir = self.log_dir

    def set_model(self, model):
        self.model = model

        self._train_dir = os.path.join(self._log_write_dir, 'train')
        self._train_step = self.model._train_counter

        self._val_dir = os.path.join(self._log_write_dir, 'validation')
        self._val_step = self.model._test_counter

        self._should_write_train_graph = False

    def on_epoch_end(self, epoch, logs=None):
        self.update_stats(**logs)

    def on_batch_end(self, batch, logs=None):
        pass

    def on_train_end(self, _):
        pass

    def update_stats(self, **stats):
        with self.writer.as_default():
            for key, value in stats.items():
                tf.summary.scalar(key, value, step = self.step)
                self.writer.flush()


class DQN(RLAgent):
    def __init__(self, env: simpy.Environment, state_dims, weights: tuple, replay_buffer, target_net_update_counter):
        super(DQN, self).__init__(env)

        # Configuration
        self._alpha = self._config.transit_agent_config.alpha
        self._gamma = self._config.transit_agent_config.gamma
        self._eps = self._config.transit_agent_config.eps
        self._tensorboard = self._config.transit_agent_config.tensorboard
        # TODO: put values below in config?
        self._eps_decay = 0.995
        self._eps_min = 0.001
        self._replay_buffer_size = 100000
        self._min_experience = 1000 # steps in replay buffer before training starts
        self._learning_rate = 0.001
        self._minibatch_size = 128
        self._target_net_update_counter = target_net_update_counter
        self._target_net_update_threshold = 200 # steps before eval net weights are propagated to target net
        self._timelimit = 60

        # Random Number Generator
        # TODO: seed?
        self._random = np.random.default_rng()

        # Neural Nets
        self._q_net = self._create_model(state_dims)
        self._target_q_net = self._create_model(state_dims)
        if weights is not None:
            if type(weights) is str:
                # filepath is given
                logging.info(f'Loading weights from {weights} ...',
                             extra={"clazz": self.__class__.__name__, "oid": ""})
                self._q_net.load_weights(weights)
                self._target_q_net.load_weights(weights)
            else:
                # weights array from previous episode is given
                # so we propagate weights from q net to target q net every episode
                eval_weights, target_weights = weights
                self._q_net.set_weights(eval_weights)

                if self._target_net_update_counter >= self._target_net_update_threshold:
                    self._target_q_net.set_weights(eval_weights)
                    self._target_net_update_counter = 0
                else:
                    self._target_q_net.set_weights(target_weights)
        else:
            # in the first episode, initialize target q net weights = q net weights
            self._target_q_net.set_weights(self._q_net.get_weights())

        # Experience Replay
        if replay_buffer is not None:
            self._replay_buffer = replay_buffer
        else:
            self._replay_buffer = deque(maxlen=self._replay_buffer_size)

        self._action_space = ActionSpace.instance()

    def _create_model(self, input_dims):
        model = keras.Sequential()
        # Input
        # model.add(layers.Conv2D(filters=256, kernel_size=(5, 5), input_shape=input_dims))
        # model.add(layers.Flatten(input_shape=input_dims))
        model.add(layers.Dense(32, input_dim=input_dims, activation='relu', kernel_initializer='he_uniform'))

        # Hidden Layers
        model.add(layers.Dense(32, activation='relu', kernel_initializer='he_uniform'))
        # model.add(layers.Dense(32))

        # Output
        model.add(layers.Dense(self._action_space.dimensionality(), activation='linear'))
        # model.compile(loss=tf.keras.losses.Huber(), optimizer='sgd', metrics=['accuracy'])
        model.compile(loss=Huber(), optimizer=Adam(learning_rate=self._learning_rate),
                      metrics=['accuracy', "mae", tf.keras.metrics.RootMeanSquaredError()])
        return model

    def run(self, bus: Bus):
        # Deep Q Learning with Experience Replay as in mnih2013 (deepmind atari paper)
        while True:
            state = deepcopy(bus._env_state) # S_t, as dict
            state_processed = self._state_to_numpy(state) # S_t, as numpy 3d matrix
            action = self._decide_next_action(bus, state_processed) # A_t, string such as "DOWN"
            action_processed = self._action_space.index(action) # A_t, index of action in action space
            yield self._env.process(self._take_action(bus, action))
            yield self._env.process(self._update_reward(bus))

            # let public transit operator track bus for visualization
            self._track(bus)

            reward = self._reward # R_t
            next_state = deepcopy(bus._env_state) # S_t, as dict
            next_state_processed = self._state_to_numpy(next_state) # S_t, as numpy 3d matrix

            reached_destination = True if bus.state is BusState.AT_TERMINAL_DESTINATION else False
            reached_timelimit = True if self._env.now - bus._spawned > self._timelimit else False

            # TODO: this is still optimistic, bus needs to move between hexagons, not euclidean/haversine
            remaining_time = self._timelimit - (self._env.now - bus._spawned)
            timeto_destination = (bus.position >> bus.route.destination) / bus._velocity
            unreachable_destination = True if remaining_time < timeto_destination else False

            terminal = reached_timelimit or reached_destination or unreachable_destination

            self._replay_buffer.append((state_processed, action_processed, reward, next_state_processed, terminal))

            self._train(terminal)

            if self._eps > self._eps_min:
                self._eps *= self._eps_decay
                self._eps = max(self._eps_min, self._eps)

            if terminal:
                break

        # retain decayed epsilon
        self._config.transit_agent_config.eps = self._eps
        logging.debug(f'Saving decayed epsilon into config: {str(self._eps)}',
                      extra={"clazz": self.__class__.__name__, "oid": bus.id})

        logging.debug(f'Current Replay Buffer size: {str(len(self._replay_buffer))}',
                      extra={"clazz": self.__class__.__name__, "oid": bus.id})

        # clean up processes
        bus._state_update_process.interrupt()
        bus._has_reached_terminal.succeed((self._q_net,
                                           self._target_q_net,
                                           self._replay_buffer,
                                           self._target_net_update_counter))

    def _track(self, bus: Bus):

        demands = bus.get_viable_demands()

        bus._agent_completed_step.succeed((bus.position, demands))
        bus._agent_completed_step = self._env.event()

    def _train(self, terminal_state: bool):
        if len(self._replay_buffer) >= self._min_experience:
            minibatch = random.sample(self._replay_buffer, self._minibatch_size)
            # minibatch = self._random.choice(self._replay_buffer, self._minibatch_size, replace=False)

            states_t = np.array([transition[0] for transition in minibatch]) # s0
            q_values_t = self._eval_predict(states_t).numpy()

            states_tp1 = np.array([transition[3] for transition in minibatch]) # s1

            # Vanilla DQN with target network
            # q_values_tp1 = self._target_predict(states_tp1).numpy()

            # Double Q-learning
            q_values_tp1 = self._eval_predict(states_tp1).numpy()
            q_values_tp1_t = self._target_predict(states_tp1).numpy()

            X = []
            y = []

            for i, (s0, a, r, s1, terminal) in enumerate(minibatch):
                if terminal:
                    target_q = r
                else:
                    # target_q = r + self._gamma * tf.math.reduce_max(q_values_tp1[i]) # vanilla DQN with target network
                    target_q = r + self._gamma * q_values_tp1_t[i][tf.math.argmax(q_values_tp1[i])] # double Q-learning

                q_values = q_values_t[i]
                q_values[a] = target_q

                X.append(s0)
                y.append(q_values)

            # try:
            #     X=tf.debugging.check_numerics(X,'X is nan')
            #     y=tf.debugging.check_numerics(y,'y is nan')
            # except tf.errors.InvalidArgumentError:
            #     pass

            self._q_net.fit(np.array(X), np.array(y), batch_size=self._minibatch_size, verbose=0, shuffle=False,
                            callbacks=[self._tensorboard] if terminal_state else None)

            self._target_net_update_counter += 1

            if self._target_net_update_counter >= self._target_net_update_threshold:
                self._target_q_net.set_weights(self._q_net.get_weights())
                self._target_net_update_counter = 0

    @tf.function
    def _target_predict(self, state):
        return self._target_q_net(state, training=False)

    @tf.function
    def _eval_predict(self, state):
        return self._q_net(state, training=False)

    def _decide_next_action(self, bus: Bus, state):
        while True:
            if np.random.rand() > self._eps:
                # q_values = self._target_net.predict(self._single_tensor_to_batch(state))[0]
                q_values = self._target_predict(tf.expand_dims(state, axis=0))
                max_q = Policy.argmax_rand(q_values)
                a = self._action_space.actions[max_q]
            else:
                a = self._action_space.sample_action_uniformly()

            if not bus.test_action(a, corridor=True):
                # hexagon is out of layer bounding box - action is forbidden
                logging.debug(f'Action {a} is forbidden, sampling again',
                              extra={"clazz": self.__class__.__name__, "oid": bus.id})
                continue
            break

        logging.debug(f'Bus takes action {a}',
                      extra={"clazz": self.__class__.__name__, "oid": bus.id})

        return a

    def _take_action(self, bus: Bus, action = None):
        """
        Actions in hexagonal grid, stay is also allowed.

                     up
                     __
        up-left    /    \  up-right
        down-left  \ __ /  down-right
                    down

        """

        if action == 'STAY':
            yield self._env.timeout(.01)
        else:
            hex_id = h3.geo_to_h3(*bus.position.getExactLocation(),
                                  resolution=self._config.transit_agent_config.action_resolution)
            new_hex = bus._geodesic_env.move_in_layer(hex_id, action)
            new_centroid = bus._geodesic_env.get_centroid(
                new_hex, f'hex_{self._config.transit_agent_config.action_resolution}')

            new_position = GeodesicPosition(*new_centroid)

            distance = bus.position >> new_position
            duration = distance / bus._velocity  # in minutes

            self._state = BusState.EN_ROUTE_DETOUR

            yield self._env.timeout(duration)

            bus._update_positions(new_position)

        bus._action_taken.succeed(action)

        return action

    def _update_reward(self, bus):

        yield bus._action_taken
        bus._action_taken = self._env.event() # only reset it after we have entered the method

        reached_destination = True if bus.state is BusState.AT_TERMINAL_DESTINATION else False
        reached_timelimit = True if self._env.now - bus._spawned > self._timelimit else False

        # TODO: this is still optimistic, bus needs to move between hexagons, not euclidean/haversine
        remaining_time = self._timelimit - (self._env.now - bus._spawned)
        timeto_destination = (bus.position >> bus.route.destination) / bus._velocity
        unreachable_destination = True if remaining_time < timeto_destination else False
        if unreachable_destination:
            logging.info(f'Episode is cancelled, destination is unreachable within time limit',
                         extra={"clazz": self.__class__.__name__, "oid": ""})

        # reward is service level (1 drop off = +1 reward)
        self._reward = bus._dropoffs # TODO: parametrize?
        if self._reward > 0:
            logging.debug(f'Service Level was increased by {str(self._reward)}',
                          extra={"clazz": self.__class__.__name__, "oid": ""})

        if (reached_timelimit and not reached_destination) or unreachable_destination:
            self._reward -= 100

        self._reward_sum = self._reward_sum + self._reward

        logging.debug(f'Current reward: {self._reward}, overall reward: {self._reward_sum}',
                      extra={"clazz": self.__class__.__name__, "oid": bus.id})

        # reset drop offs
        bus._dropoffs = 0

        # bus._agent_completed_step.succeed((before_state, action, self._reward, self._reward_sum))
        # bus._agent_completed_step.succeed(self._reward_sum)

    def _state_to_tensor(self, state: dict):
        # tensor of corridor dim * corridor dim + corridor dim + 1
        # 1) OD demands (matrix) 2) agent position (one hot vector), 3) driving time (scalar)
        return tf.convert_to_tensor(self._state_to_numpy(state), tf.dtypes.int32)

    @staticmethod
    def _state_to_numpy(state: dict):
        # ndarray of corridor dim * corridor dim + corridor dim + 1
        # 1) OD demands (matrix) 2) agent position (one hot vector), 3) driving time (scalar)
        # TODO: add "dtype=int" to concatenate call when numpy >= 1.20.0 in environment
        return np.concatenate((state['demands'].reshape(-1), state['position'], [state['drivingtime']]))

    @staticmethod
    def _single_tensor_to_batch(tensor):
        return tf.reshape(tensor, (-1, *tensor.shape))
