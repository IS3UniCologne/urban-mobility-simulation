import logging
import os
import random
from collections import deque
from copy import deepcopy

import h3
import numpy as np
import simpy
import tensorflow as tf
from keras.callbacks import TensorBoard
from keras.optimizer_v2.learning_rate_schedule import ExponentialDecay
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.losses import Huber
from tensorflow.keras.optimizers import Adam

from simulation.agent.action_space import ActionSpace
from simulation.agent.policy import Policy
from simulation.agent.rl_agent import RLAgent
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.time import SimulationTimeConverter
from simulation.vehicle.public_transit_bus import Bus, PublicTransitVehicleState


class ModifiedTensorBoard(TensorBoard):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.step = 1
        self.writer = tf.summary.create_file_writer(self.log_dir)
        self._log_write_dir = self.log_dir

    def set_model(self, model):
        self.model = model

        self._train_dir = os.path.join(self._log_write_dir, "train")
        self._train_step = self.model._train_counter

        self._val_dir = os.path.join(self._log_write_dir, "validation")
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
                tf.summary.scalar(key, value, step=self.step)
                self.writer.flush()


class DQN(RLAgent):
    def __init__(
        self,
        env: simpy.Environment,
        state_dims,
        weights: tuple,
        replay_buffer,
        episode=1,
    ):
        super(DQN, self).__init__(env)

        self._total_episodes = self._config.transit_agent_config.episodes
        self._episode = episode  # starting from 1
        self._action_space = ActionSpace.instance()

        # Configuration
        self._alpha = self._config.transit_agent_config.alpha
        self._gamma = self._config.transit_agent_config.gamma
        if self._config.transit_agent_config.evaluation:
            self._eps = self._eps_min = 0
        else:
            self._eps_min = self._config.transit_agent_config.eps_min
            self._eps = self._config.transit_agent_config.eps
        self._eps_decay_strategy = self._config.transit_agent_config.eps_decay_strategy
        self._eps_decay = self._config.transit_agent_config.eps_decay
        self._eps_min = self._config.transit_agent_config.eps_min
        self._penalty = self._config.transit_agent_config.penalty
        self._reward = self._config.transit_agent_config.reward
        self._replay_buffer_size = (
            self._config.transit_agent_config.buffersize
        )  # size in episodes
        self._min_experience = (
            self._config.transit_agent_config.min_experience
        )  # episodes in replay buffer before training starts
        self._use_double_q = (
            self._config.transit_agent_config.double_q
        )  # usage of Double Q Learning (Hasselt 2016)
        self._minibatch_size = (
            self._config.transit_agent_config.batchsize
        )  # training minibatch size
        self._target_net_update_threshold = (
            self._config.transit_agent_config.target_update_threshold
        )  # training steps before q net weights are propagated to target q net
        self._tau = self._config.transit_agent_config.tau
        self._learning_rate = None
        self._learning_rate_decay_steps = (
            self._config.transit_agent_config.lr_decay_steps
        )

        # tuple of dim (1, n hidden layers+1 for input layer),
        # output layer is fixed to n actions
        self._q_net_layer = self._config.transit_agent_config.q_net_layer

        # decay exponentially from initial_learning_rate to initial_learning_rate * decay_rate over decay_steps steps
        # lr = initial_learning_rate * decay_rate ^ (step / decay_steps)
        if self._config.transit_agent_config.lr_decay:
            self._learning_rate = ExponentialDecay(
                initial_learning_rate=0.01,
                decay_steps=self._learning_rate_decay_steps,
                decay_rate=0.1,
            )
        else:
            self._learning_rate = 0.001  # adam default learning rate

        if self._config.transit_agent_config.optimizer is None:
            self._optimizer = Adam(learning_rate=self._learning_rate)
        else:
            self._optimizer = self._config.transit_agent_config.optimizer

        self._tensorboard = self._config.transit_agent_config.tensorboard

        # Random Number Generator
        # TODO: seed?
        self._random = np.random.default_rng()

        # Neural Nets
        self._q_net = self._create_model(state_dims)
        self._target_q_net = self._create_model(state_dims)
        if weights is not None:
            if type(weights) is str:
                # filepath is given
                logging.info(
                    f"Loading weights from {weights} ...",
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )
                self._q_net.load_weights(weights)
                self._target_q_net.load_weights(weights)
            else:
                # weights array from previous episode is given
                eval_weights, target_weights = weights
                self._q_net.set_weights(eval_weights)
                self._target_q_net.set_weights(target_weights)
        else:
            logging.debug(
                self._q_net.summary(),
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

            # in the first episode, initialize target q net weights = q net weights
            self._target_q_net.set_weights(self._q_net.get_weights())

        # Experience Replay
        if replay_buffer is not None:
            if isinstance(replay_buffer, deque):
                self._replay_buffer = replay_buffer
            else:
                # use list as long as buffer size is not reached, then use deque
                if self._episode <= self._replay_buffer_size:
                    self._replay_buffer = replay_buffer
                else:
                    self._replay_buffer = deque(
                        replay_buffer, maxlen=len(replay_buffer)
                    )
        else:
            self._replay_buffer = []

    def _create_model(self, input_dims):
        model = keras.Sequential()

        # Input
        model.add(
            layers.Dense(
                self._q_net_layer[0],
                input_dim=input_dims,
                activation="tanh",
                kernel_initializer="glorot_uniform",
            )
        )

        # Hidden Layers
        for layernodes in self._q_net_layer[1:]:
            model.add(
                layers.Dense(
                    layernodes, activation="tanh", kernel_initializer="glorot_uniform"
                )
            )

        # Output
        model.add(
            layers.Dense(self._action_space.dimensionality(), activation="linear")
        )
        # model.compile(loss=tf.keras.losses.Huber(), optimizer='sgd', metrics=['accuracy'])
        model.compile(loss=Huber(), optimizer=self._optimizer, metrics=["accuracy"])

        return model

    def run(self, bus: Bus):
        # set timelimit to multiplier specified in config * planned route total time
        route_duration = SimulationTimeConverter.duration_between(
            bus.route.origin.departure, bus.route.destination.departure
        )
        self._timelimit = (
            self._config.transit_agent_config.timelimit_multiplier * route_duration
        )
        # self._timelimit = 60

        # Deep Q Learning with Experience Replay as in mnih2013 (deepmind atari paper)
        while True:
            state = deepcopy(bus._env_state)  # S_t, as dict
            state_processed = self._state_to_numpy(state)  # S_t, as numpy 3d matrix
            action = self._decide_next_action(
                bus, state_processed
            )  # A_t, string such as "DOWN"
            action_processed = self._action_space.index(
                action
            )  # A_t, index of action in action space
            yield self._env.process(self._take_action(bus, action))
            yield self._env.process(self._update_reward(bus))

            # let public transit operator track bus for visualization
            self._track(bus)

            reward = self._latest_reward  # R_t
            next_state = deepcopy(bus._env_state)  # S_t, as dict
            next_state_processed = self._state_to_numpy(
                next_state
            )  # S_t, as numpy 3d matrix

            reached_destination = (
                True
                if bus.state is PublicTransitVehicleState.AT_TERMINAL_DESTINATION
                else False
            )
            reached_timelimit = (
                True if self._env.now - bus._spawned > self._timelimit else False
            )

            # TODO: this is still optimistic, bus needs to move between hexagons, not euclidean/haversine
            remaining_time = self._timelimit - (self._env.now - bus._spawned)
            timeto_destination = (bus.position >> bus.route.destination) / bus._velocity
            unreachable_destination = (
                True if remaining_time < timeto_destination else False
            )
            # unreachable_destination = False # JUST FOR DEBUGGING

            terminal = (
                reached_timelimit or reached_destination or unreachable_destination
            )

            self._replay_buffer.append(
                (
                    state_processed,
                    action_processed,
                    reward,
                    next_state_processed,
                    terminal,
                )
            )

            if not self._config.transit_agent_config.evaluation:
                self._train(terminal)

            if terminal:
                if self._eps_decay_strategy != "none":
                    # decay epsilon at end of episode
                    if self._eps > self._eps_min:
                        if self._eps_decay_strategy == "exp":
                            # actually a power law function decay
                            self._eps *= self._eps_decay
                        elif self._eps_decay_strategy == "linear":
                            # decay linearly from 1 to 0 over all episodes
                            self._eps = 1 - (1 / self._total_episodes) * self._episode
                        self._eps = max(self._eps_min, self._eps)
                break

        # retain decayed epsilon
        self._config.transit_agent_config.eps = self._eps
        logging.debug(
            f"Saving decayed epsilon into config: {str(self._eps)}",
            extra={"clazz": self.__class__.__name__, "oid": f"Episode {self._episode}"},
        )

        # retain optimizer steps for decayed learning rate
        self._config.transit_agent_config.optimizer = self._optimizer
        if self._config.transit_agent_config.lr_decay:
            logging.debug(
                f"Saving decayed learning rate into config: {str(self._learning_rate(self._optimizer.iterations))}",
                extra={
                    "clazz": self.__class__.__name__,
                    "oid": f"Episode {self._episode}",
                },
            )

        logging.debug(
            f"Current Replay Buffer size: {str(len(self._replay_buffer))}",
            extra={"clazz": self.__class__.__name__, "oid": f"Episode {self._episode}"},
        )

        # clean up processes
        bus._state_update_process.interrupt()

        # stop demand generation
        bus._world.stop_all_processes()

        # retain parameters
        # TODO: refactor such that weights etc are retained through config instead of being passed around?

        duration = (
            self._env.now - bus._spawned if reached_destination else None
        )  # None if episode is canceled
        distance = bus._dist_traveled if reached_destination else None
        bus._has_reached_terminal.succeed(
            (
                self._q_net,
                self._target_q_net,
                self._replay_buffer,
                self._episode,
                (
                    self._learning_rate(self._optimizer.iterations)
                    if self._config.transit_agent_config.lr_decay
                    else 0.001
                ),
                reached_destination,
                distance,
                duration,
            )
        )

    def _track(self, bus: Bus):
        demands = bus.get_viable_demands()

        bus._agent_completed_step.succeed((bus.position, demands))
        bus._agent_completed_step = self._env.event()

    def _train(self, terminal_state: bool):
        if self._episode >= self._min_experience:
            minibatch = random.sample(self._replay_buffer, self._minibatch_size)
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
                        target_q = (
                            r
                            + self._gamma
                            * q_values_tp1_t[i][tf.math.argmax(q_values_tp1[i])]
                        )  # double Q-learning
                    else:
                        target_q = r + self._gamma * tf.math.reduce_max(
                            q_values_tp1[i]
                        )  # vanilla DQN with target network

                q_values = q_values_t[i]
                q_values[a] = target_q

                X.append(s0)
                y.append(q_values)

            self._q_net.fit(
                np.array(X),
                np.array(y),
                batch_size=self._minibatch_size,
                verbose=0,
                shuffle=False,
                callbacks=[self._tensorboard] if terminal_state else None,
            )

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
        return self._target_q_net(state, training=False)

    @tf.function
    def _eval_predict(self, state):
        return self._q_net(state, training=False)

    def _decide_next_action(self, bus: Bus, state):
        rand = True if np.random.rand() <= self._eps else False

        while True:
            if not rand:
                q_values = self._target_predict(tf.expand_dims(state, axis=0))
                # TODO: normalize / probabilities instead of argmax?
                max_q = Policy.argmax_rand(q_values)
                a = self._action_space.actions[max_q]
                rand = True  # otherwise this blocks forever when a is forbidden
            else:
                a = self._action_space.sample_action_uniformly()

            if not bus.test_action(a, corridor=True):
                # hexagon is out of layer bounding box - action is forbidden
                logging.debug(
                    f"Action {a} is forbidden, sampling again",
                    extra={"clazz": self.__class__.__name__, "oid": bus.id},
                )
                continue
            break

        logging.debug(
            f"Bus takes action {a}",
            extra={"clazz": self.__class__.__name__, "oid": bus.id},
        )

        return a

    def _take_action(self, bus: Bus, action=None):
        """
        Actions in hexagonal grid, stay is also allowed.

                     up
                     __
        up-left    /    \\  up-right
        down-left  \\ __ /  down-right
                    down

        """

        if action == "STAY":
            # even though the bus does not move, timeout for the average movement duration
            # otherwise the action does have no consequence, when another action immediately follows
            yield self._env.timeout(
                h3.edge_length(
                    resolution=self._config.transit_agent_config.action_resolution,
                    unit="m",
                )
                / bus._velocity
            )
        else:
            hex_id = h3.geo_to_h3(
                *bus.position.getExactLocation(),
                resolution=self._config.transit_agent_config.action_resolution,
            )
            new_hex = bus._geodesic_env.move_in_layer(hex_id, action)
            new_centroid = bus._geodesic_env.get_centroid(
                new_hex, f"hex_{self._config.transit_agent_config.action_resolution}"
            )

            new_position = GeodesicPosition(*new_centroid)

            distance = bus.position >> new_position
            bus._dist_traveled += distance  # add to overall travel distance
            duration = distance / bus._velocity  # in minutes

            self._state = PublicTransitVehicleState.EN_ROUTE_DETOUR

            yield self._env.timeout(duration)

            bus._update_positions(new_position)

        bus._action_taken.succeed(action)

        return action

    def _update_reward(self, bus):
        yield bus._action_taken
        bus._action_taken = (
            self._env.event()
        )  # only reset it after we have entered the method

        reached_destination = (
            True
            if bus.state is PublicTransitVehicleState.AT_TERMINAL_DESTINATION
            else False
        )
        reached_timelimit = (
            True if self._env.now - bus._spawned > self._timelimit else False
        )

        # TODO: this is still optimistic, bus needs to move between hexagons, not euclidean/haversine
        remaining_time = self._timelimit - (self._env.now - bus._spawned)
        timeto_destination = (bus.position >> bus.route.destination) / bus._velocity
        unreachable_destination = True if remaining_time < timeto_destination else False
        # unreachable_destination = False # JUST FOR DEBUGGING
        if unreachable_destination:
            logging.info(
                "Episode is cancelled, destination is unreachable within time limit",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

        # reward is service level (1 drop off = +1 reward)
        self._latest_reward = bus._dropoffs * self._reward
        if self._latest_reward > 0:
            logging.debug(
                f"Service Level was increased by {str(self._latest_reward)}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

        if (reached_timelimit and not reached_destination) or unreachable_destination:
            self._latest_reward -= self._penalty

        self._reward_sum = self._reward_sum + self._latest_reward

        logging.debug(
            f"Current reward: {self._latest_reward}, overall reward: {self._reward_sum}",
            extra={"clazz": self.__class__.__name__, "oid": bus.id},
        )

        # reset drop offs
        bus._dropoffs = 0

        # bus._agent_completed_step.succeed((before_state, action, self._latest_reward, self._reward_sum))
        # bus._agent_completed_step.succeed(self._reward_sum)

    def _state_to_tensor(self, state: dict):
        # tensor of corridor dim * corridor dim + corridor dim + 1
        # 1) OD demands (matrix) 2) agent position (one hot vector), 3) driving time (scalar)
        return tf.convert_to_tensor(self._state_to_numpy(state), tf.dtypes.int32)

    @staticmethod
    def _state_to_numpy(state: dict):
        # ndarray of corridor dim * corridor dim + corridor dim + 1
        # 1) OD demands (matrix) 2) agent position (one hot vector), 3) remaining driving time (scalar)
        # TODO: add "dtype=int" to concatenate call when numpy >= 1.20.0 in environment
        return np.concatenate(
            (state["demands"].reshape(-1), state["position"], [state["remaining_time"]])
        )

    @staticmethod
    def _single_tensor_to_batch(tensor):
        return tf.reshape(tensor, (-1, *tensor.shape))
