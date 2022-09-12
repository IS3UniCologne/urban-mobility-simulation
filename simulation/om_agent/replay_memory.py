import numpy as np


class ReplayMemory:
    def __init__(self, max_size, state_dim, batch_size):
        self.mem_size = max_size
        self.mem_cntr = 0
        self.state_memory = np.array([np.zeros(state_dim)] * self.mem_size)
        self.next_state_memory = np.array([np.zeros(state_dim)] * self.mem_size)
        self.action_memory = np.array([np.zeros(1)] * self.mem_size)
        self.reward_memory = np.array(np.zeros(self.mem_size))

        self._batch_size = batch_size

    def store_transition(self, state, action, reward, next_state):
        """Store state, action, reward, next_state in Replay Memory
        """

        # calculate input index
        index = self.mem_cntr % self.mem_size

        # input elements from the beginning of the list
        self.state_memory[index] = state
        self.next_state_memory[index] = next_state
        self.action_memory[index] = action
        self.reward_memory[index] = reward

        # count elements that were ever inserted
        self.mem_cntr += 1

    def sample_memory(self, batch_size):
        """Sample state, action, reward, next_state form replay buffer
        """

        # only needed if buffer is not full yet
        max_mem = min(self.mem_cntr, self.mem_size)

        # sample random indices
        batch = np.random.choice(max_mem, batch_size)
        states = self.state_memory[batch]
        next_states = self.next_state_memory[batch]
        actions = self.action_memory[batch]
        rewards = self.reward_memory[batch]

        return states, actions, rewards, next_states

    def get_mem_cntr(self):
        return self.mem_cntr

    @property
    def batch_size(self):
        return self._batch_size