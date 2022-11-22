import logging
import sys
from collections import deque
from copy import deepcopy
import numpy as np
import random
import torch
from torch import nn
from torch import optim

from learning.interface.learning_interface import LearningInterface
from learning.helper.policy import Policy
from learning.agents.rl_agent import RLAgent
from learning.spaces.action_space import ActionForbidden
from simulation.helper.configuration.configuration import Configuration


class DQNN(nn.Module):
    def __init__(self, input_layer, action_layer):
        super(DQNN, self).__init__()

        self._config = Configuration.instance()

        self.layers = nn.Sequential(
            nn.Linear(input_layer, self._config.DQN_config.q_net_layer[0]),
            nn.ReLU(),
            nn.Linear(self._config.DQN_config.q_net_layer[0], self._config.DQN_config.q_net_layer[1]),
            nn.ReLU(),
            nn.Linear(self._config.DQN_config.q_net_layer[1], action_layer)
        )

    def forward(self, x):
        return self.layers(x)


class DQN(RLAgent):
    def __init__(self, problem: LearningInterface):
        super(DQN, self).__init__()

        # Get cpu or gpu device for training.
        self._device = "cpu"
        if torch.cuda.is_available():
            self._device = "cuda"
        elif torch.backends.mps.is_available():
            self._device = "mps"
        logging.debug(f"Using {self._device} device",
                      extra={"clazz": self.__class__.__name__, "oid": ""})

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

        # Experience Replay
        self._replaybuffer_size = self._config.DQN_config.replaybuffer_size  # size in episodes
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
            raise NotImplemented
        else:
            self._learning_rate = 0.001  # adam default learning rate

        self._loss_fn = nn.SmoothL1Loss()

        self._tensorboard = self._config.DQN_config.tensorboard

        # Random Number Generator
        # TODO: seed?
        self._random = np.random.default_rng()

        # defer model creation until the problem has initialized properly
        # this is important for problems where e.g. the state dimensions change depending on the problem instance
        self._q_net = None
        self._target_q_net = None
        self._init_process = self.problem.env.process(self._delayed_init())

    def _delayed_init(self):
        yield self.problem.initialized

        # Neural Nets
        self._q_net = DQNN(self.problem.state_size_flattened,
                           self._action_space.num_choices()).to(self._device)
        self._target_q_net = DQNN(self.problem.state_size_flattened,
                           self._action_space.num_choices()).to(self._device)

        if self._config.DQN_config.weights is not None:
            if type(self._config.DQN_config.weights) is str:
                # filepath is given
                logging.info(f'Loading model state_dict from {self._config.DQN_config.weights} ...',
                             extra={"clazz": self.__class__.__name__, "oid": ""})
                self._q_net.load_state_dict(torch.load(self._config.DQN_config.weights))
                self._target_q_net.load_state_dict(torch.load(self._config.DQN_config.weights))
            else:
                # weights array from previous episode is given
                eval_weights, target_weights = self._config.DQN_config.weights
                self._q_net.load_state_dict(eval_weights)
                self._target_q_net.load_state_dict(target_weights)
        else:
            logging.debug("Model Summary:",
                          extra={"clazz": self.__class__.__name__, "oid": ""})
            logging.debug(self._q_net)

            # in the first episode, initialize target q net weights = q net weights
            self._target_q_net.load_state_dict(self._q_net.state_dict())

        self._target_q_net.eval()

        self._optimizer = optim.Adam(params=self._q_net.parameters(), lr=self._learning_rate)
        if self._config.DQN_config.optimizer is not None:
            self._optimizer.load_state_dict(self._config.DQN_config.optimizer)

    def run(self):
        if self._config.DQN_config.evaluation:
            yield self.problem.env.process(self.use())
        else:
            yield self.problem.env.process(self.learn())

    def use(self):
        # Deep Q Learning with Experience Replay as in mnih2013 (deepmind atari paper)
        while True:
            state = torch.from_numpy(self.problem.state()).to(self._device) # S_t, as numpy 3d matrix -> torch tensor
            action = self.policy(state)  # A_t, string such as "DOWN"
            try:
                _, reward, finished = yield self.problem.env.process(self.problem.step(action))
            except ActionForbidden:
                continue
            if finished:
                break

    def learn(self):

        # Deep Q Learning with Experience Replay as in mnih2013 (deepmind atari paper)
        actions_tried = set()
        while True:

            state = torch.from_numpy(self.problem.state()).to(self._device) # S_t, as numpy 3d matrix -> torch tensor
            try:
                action = self.policy(state)  # A_t, string such as "DOWN"
            except TypeError as e:
                # logging.error(e)
                # TODO: q net does not get initialized at times
                # self.problem._initialized = self.problem.env.event()
                # self.problem.initialized.succeed()

                # a simple "try that again" will work
                continue
            if action in actions_tried:
                continue
            actions_tried.add(action)
            action_index = self._action_space.index(action)  # A_t, index of action in action space

            try:
                next_state, reward, finished = yield self.problem.env.process(self.problem.step(action))
                actions_tried.clear()
            except ActionForbidden:
                if len(actions_tried) == self._action_space.num_choices():
                    logging.error(f'Deadlock encountered! All actions tried, all forbidden!',
                          extra={"clazz": self.__class__.__name__, "oid": ""})
                    sys.exit(1)
                continue

            self._cumulative_reward += reward
            logging.debug(f'Current reward: {reward}, overall reward: {self._cumulative_reward}',
                          extra={"clazz": self.__class__.__name__, "oid": ""})

            # -> torch tensor
            action_index = torch.tensor(action_index).to(self._device)
            next_state = torch.from_numpy(next_state).to(self._device)
            reward = torch.tensor(reward).to(self._device)

            self._replaybuffer.append((state, action_index, reward, next_state, finished))
            if self._episode >= self._min_experience:
                self._train()

            if finished:
                if self._episode >= self._min_experience and self._episode % self._target_net_update_threshold == 0:
                    # propagate parameters to target network
                    if self._tau is not None:
                        # do soft updates
                        for target_param, param in zip(self._target_q_net.parameters(), self._q_net.parameters()):
                            target_param.data.copy_(target_param.data * (1.0 - self._tau) + param.data * self._tau)
                    else:
                        # do hard updates
                        self._target_q_net.load_state_dict(self._q_net.state_dict())

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
        self._config.DQN_config.optimizer = self._optimizer.state_dict()

        if self._config.DQN_config.lr_decay:
            raise NotImplemented
            # logging.debug(
            #     f'Saving decayed learning rate into config: {str(self._learning_rate(self._optimizer.iterations))}',
            #     extra={"clazz": self.__class__.__name__, "oid": f'Episode {self._episode}'})

        # retain replaybuffer
        self._config.DQN_config.replaybuffer = self._replaybuffer
        logging.debug(f'Saving replay buffer into config. Size: {str(len(self._replaybuffer))}',
                      extra={"clazz": self.__class__.__name__, "oid": f'Episode {self._episode}'})

        # retain weights
        self._config.DQN_config.weights = (self._q_net.state_dict(), self._target_q_net.state_dict())
        logging.debug(f'Saving model weights into config.',
                      extra={"clazz": self.__class__.__name__, "oid": f'Episode {self._episode}'})

        self._tensorboard.flush()

        self.problem.reset()

    def policy(self, state):
        rand = True if np.random.rand() <= self._eps else False

        if not rand:
            with torch.no_grad():
                q_values = self._q_net(state)
            a = self._action_space.actions[q_values.argmax()] # TODO: tiebreak instead of choosing first argmax
        else:
            a = self._action_space.sample_action_uniformly()

        return a

    def _train(self):
        minibatch = random.sample(self._replaybuffer, self._minibatch_size)

        # Q(s,a) using policy net
        states_t = torch.stack([transition[0] for transition in minibatch])  # s0
        actions_t = torch.vstack([transition[1] for transition in minibatch]) # a0
        q_values = self._q_net(states_t).gather(1, actions_t)

        if self._use_double_q:
            # TODO: Double Q-Learning
            raise NotImplemented
        else:
            # Vanilla DQN using target net

            states_tp1 = torch.stack([transition[3] for transition in minibatch])  # s1
            rewards = torch.stack([transition[2] for transition in minibatch]) # r
            q_values_tp1 = self._target_q_net(states_tp1).max(dim=1)[0].detach() # best next Q

            # # r * \gammma * argmax(a in A) Q(s',A)
            q_estimates = (rewards + (self._gamma * q_values_tp1)).unsqueeze(dim=1)

            # update q_estimates to reward when s' is terminal
            terminal_mask = torch.tensor(tuple([transition[4] for transition in minibatch]),
                                         device=self._device, dtype=torch.bool)
            q_estimates[terminal_mask] = rewards[terminal_mask].unsqueeze(dim=1)

        loss = self._loss_fn(q_values, q_estimates)

        self._tensorboard.add_scalar('loss', loss, f'{self._episode}{int(self.problem.env.now)}')

        self._optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_value_(self._q_net.parameters(), 1) # clip gradients to (-1,1)
        self._optimizer.step()
