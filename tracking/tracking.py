import logging
from typing import Any, Tuple  # noqa: UP035

from beartype.door import is_bearable  # like "isinstance(...)"
from simpy import Environment

from simulation.helper.simulation_base import SimulationBase
from tracking.tracking_interface import TrackingInterface


class Tracking(SimulationBase):
    slots__ = ("__env", "tracked")
    """
    Singleton Class that controls all tracking and communication of tracking-exposed values in the simulation to
    external logic.
    """

    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> "Tracking":
        """Static access method"""
        if Tracking.__instance is None:
            raise Exception("Tracking was not initialized")
        else:
            return Tracking.__instance

    @staticmethod
    def init(env):  # noqa: ANN001, ANN205
        """Static init method"""
        if Tracking.__instance is None:
            Tracking(env)
        return Tracking.__instance

    def __init__(self, env: Environment):  # noqa: ANN204
        """Virtually private constructor"""
        if Tracking.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Tracking.__instance = self
            super(Tracking, self).__init__()  # noqa: UP008

        self.__env = env
        self.tracked = {}

    def register(self, to_track: TrackingInterface, id: int | None = None) -> str:
        """

        :param to_track: Agent (user, vehicle, ...) or resource in the simulation to register with the tracking. Must
        implement TrackingInterface
        :return: uid
        """

        classname = to_track.__class__.__name__
        if id is None:
            try:
                id = to_track.id
            except AttributeError:
                # no id associated, is it a single class instance? (like operator)
                id = "singleton"
        uid = f"{classname}_{id}"

        if not isinstance(to_track, TrackingInterface):
            raise NotImplementedError(
                f"Something tried to register {classname}, but it"
                f"does not implement the necessary TrackingInterface!"
            )
        self.tracked[uid] = {"class": classname, "id": id, "reference": to_track}
        logging.debug(
            f"Registered {classname} with ID {id}",  # noqa: G004
            extra={"uid": self.__class__.__name__},
        )

        return uid

    def unregister_by_uid(self, uid: str):  # noqa: ANN201
        try:
            result = self.tracked.pop(uid)
            logging.debug(
                f"Unregistered {result['class']} with ID {result['id']}",  # noqa: G004
                extra={"uid": self.__class__.__name__},
            )
        except KeyError:
            logging.warning(
                f"Trying to unregister uid {uid}, but this uid is currently not tracked!",  # noqa: G004
                extra={"uid": self.__class__.__name__},
            )

    def unregister_by_obj(self, to_untrack: TrackingInterface):  # noqa: ANN201
        uid = self._get_uid(to_untrack)
        self.unregister_by_uid(uid)

    def get(self, obj, attribute) -> Any:  # noqa: ANN001, ANN401
        if isinstance(obj, str):
            uid = obj
        elif isinstance(obj, object):
            uid = self._get_uid(obj)
        try:
            return self.__env.now, self.tracked[uid]["reference"].get(attribute)
        except (KeyError, PermissionError) as e:
            if type(e) is KeyError:
                logging.error(
                    f"Trying to access {attribute} of uid {obj}, but this uid is currently not tracked!",  # noqa: G004
                    extra={"uid": self.__class__.__name__},
                )
                return None
            elif type(e) is PermissionError:
                logging.error(
                    f"{attribute} of uid {obj} is not exposed or does not exist!",  # noqa: G004
                    extra={"uid": self.__class__.__name__},
                )
                return None

    def dump(self, uid, exposed_only: bool = True) -> Tuple[float, dict] | None:  # noqa: ANN001, UP006
        try:
            return self.__env.now, self.tracked[uid]["reference"].dump(exposed_only)
        except KeyError:
            logging.error(
                f"Trying to dump attributes of uid {uid}, but this uid is currently not tracked!",  # noqa: G004
                extra={"uid": self.__class__.__name__},
            )
            return None

    def list_tracked(self, cls: type | str) -> list:
        """
        List tracked uid's of the specific class requested

        :param cls: class type to list, fallback is classname as str
        :return: list of uid
        """

        if isinstance(cls, str):
            return [x for x, y in self.tracked.items() if y["class"] == cls]
        return [x for x, y in self.tracked.items() if is_bearable(y["reference"], cls)]

    def _get_object(self, uid) -> TrackingInterface | None:  # noqa: ANN001
        """
        It is discouraged to use this method extensively, rather use the get() and dump() methods that tracking exposes.

        :param uid: tracking-internal unique identifier of the object
        :return: object that implements TrackingInterface
        """
        try:
            return self.tracked[uid]["reference"]
        except KeyError:
            logging.error(
                f"Trying to access object at uid {uid}, but this uid is currently not tracked!",  # noqa: G004
                extra={"uid": self.__class__.__name__},
            )
            return None

    def _get_uid(self, object: TrackingInterface) -> str:
        """
        Internal-use method for getting the inferred uid of an object

        :param object: A TrackingInterface-implementing object
        :return: uid
        """
        classname = object.__class__.__name__
        try:
            uid = f"{classname}_{object._id}"  # noqa: SLF001
        except AttributeError:
            # no id associated, is it a single class instance? (like operator)
            uid = f"{classname}_singleton"

        if uid not in self.tracked:
            logging.warning(
                f"Generated uid for object at uid {uid}, but this uid is currently not tracked!",  # noqa: G004
                extra={"uid": self.__class__.__name__},
            )

        return uid
