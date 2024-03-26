from abc import ABC, abstractmethod


class Environment(ABC):
    def __init__(self):
        self._layer = {}  # name: layer frame

    @property
    def layer(self):
        return self._layer

    @abstractmethod
    def getLayer(self, layer_name):
        pass

    @abstractmethod
    def addLayer(self, layer_name, layer):
        pass
