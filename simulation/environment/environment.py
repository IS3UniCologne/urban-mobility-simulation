from abc import ABC, abstractmethod  # noqa: D100


class Environment(ABC):  # noqa: D101
    # TODO: not really an ABC with init
    __slots__ = ("_layer",)

    def __init__(self) -> None:
        self._layer = {}  # name: layer frame

    @property
    def layer(self):  # noqa: ANN201, D102
        return self._layer

    @abstractmethod
    def getLayer(self, layer_name) -> None:  # noqa: ANN001, D102
        pass

    @abstractmethod
    def addLayer(self, layer_name, layer) -> None:  # noqa: ANN001, D102
        pass
