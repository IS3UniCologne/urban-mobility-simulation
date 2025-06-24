from abc import ABC, abstractmethod


class Environment(ABC):
    __slots__ = ("_layer",)

    def __init__(self) -> None:
        self._layer = {}  # name: layer frame

    @property
    def layer(self):  # noqa: ANN201
        return self._layer

    @abstractmethod
    def getLayer(self, layer_name) -> None:  # noqa: ANN001
        pass

    @abstractmethod
    def addLayer(self, layer_name, layer) -> None:  # noqa: ANN001
        pass
