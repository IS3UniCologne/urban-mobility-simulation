from abc import ABC, abstractmethod

class Position(ABC):

    @abstractmethod
    def __init__(self):
        self._x = "I have a x position"
        self._y = "I have a y position"

    @abstractmethod
    def getExactLocation(self):
        pass

    @abstractmethod
    def __str__(self):
        pass