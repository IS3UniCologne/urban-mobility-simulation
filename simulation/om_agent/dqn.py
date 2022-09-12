from simulation.om_agent.generic_network import GenericNetwork
import torch as T
import torch.optim as optim
import sys

class DQN(GenericNetwork):

    def __init__(self, lr, input_dims: int, layer_dims: list, output_dims: int,
                 nn_seed: int):
        super().__init__(lr, input_dims, layer_dims, output_dims, nn_seed)

    def forward(self, state: T.tensor):

        return self._layers(state)
