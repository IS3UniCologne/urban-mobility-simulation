from abc import ABC, abstractmethod

class Environment(ABC):
    def __init__(self):
        self._layer = []

    @abstractmethod
    def getLayers(self):
        pass