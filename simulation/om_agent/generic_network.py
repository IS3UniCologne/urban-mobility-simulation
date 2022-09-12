import torch as T
import torch.nn as nn
import torch.optim as optim
from abc import ABC, abstractmethod


class GenericNetwork(nn.Module, ABC):
    def __init__(self, lr, input_dims: int, layer_dims: list,
                 output_dims: int, seed: int):
        super(GenericNetwork, self).__init__()
        self._input_dims = input_dims
        self._output_dims = output_dims
        self._seed = seed

        layers = []

        # set manual seed
        #T.manual_seed(self._seed)

        # first layer
        fc_first = nn.Linear(self._input_dims, layer_dims[0])
        layers.extend([fc_first, nn.ReLU()])

        # hidden layers
        for i in range(len(layer_dims) - 1):
            layers.extend([nn.Linear(layer_dims[i], layer_dims[i + 1]),
                           nn.ReLU()])

        # last layer
        fc_last = nn.Linear(layer_dims[-1], self._output_dims)
        layers.extend([fc_last])#, nn.ReLU()])

        self._layers = nn.Sequential(*layers)

        self.optimizer = optim.Adam(self.parameters(), lr=lr)
        self.device = T.device('cuda:0' if T.cuda.is_available() else 'cpu')
        self.to(self.device)

    @abstractmethod
    def forward(self, network_input):
        pass

    @property
    def input_dims(self):
        return self._input_dims

    @property
    def output_dims(self):
        return self._output_dims