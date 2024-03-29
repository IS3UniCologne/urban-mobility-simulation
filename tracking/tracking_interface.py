import logging
from abc import ABC, abstractmethod, abstractproperty


class TrackingInterface(ABC):
    """
    This interface must be implemented by every agent in the simulation that should be trackable by any means from
    outside the main simulation. Trackable objects must explicitly initialize the "exposes" attribute with a list of
    attributes (non-private) that are exposed.
    """

    exposes: list = NotImplemented

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.exposes is NotImplemented:
            raise NotImplementedError(
                "Please implement the `exposes` class variable for any class that implements the"
                "TrackingIntercace AbstractBaseClass"
            )

    def get(self, attribute: str):
        if attribute in self.exposes and hasattr(self, attribute):
            return self.__getattribute__(attribute)
        else:
            logging.debug(
                f"Tracking tried to request an unexposed or private attribute ({attribute}) from this object",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )
            raise PermissionError

    @abstractmethod
    def dump(self, exposed_only: bool = True) -> dict:
        """
        This method should dump all attributes that are requestable into a dictionary with keys being the attribute name
        This method can be implemented differently to ensure only attributes that should be monitored in a dump are
        included. This is especially important for "old" agents that do not implement private attributes. There, all
        attributes would be dumped otherwise, leading to overhead.

        :param exposed_only: Can optionally be set to False to dump more than only explicitly exposed attributes,
        subject to the implementation of this method. Default: True
        :return: dictionary of type {attribute name: attribute value}
        """
        pass
