import logging
from typing import Any, Optional, Tuple

from simpy import Environment

from tracking.tracking_interface import TrackingInterface


class Tracking:
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
    def init(env):
        """Static init method"""
        if Tracking.__instance is None:
            Tracking(env)
        return Tracking.__instance

    def __init__(self, env: Environment):
        """Virtually private constructor"""
        if Tracking.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Tracking.__instance = self
            super(Tracking, self).__init__()

        self.__env = env
        self.tracked = {}

    def register(self, to_track: TrackingInterface) -> str:
        """

        :param to_track: Agent (user, vehicle, ...) or resource in the simulation to register with the tracking. Must
        implement TrackingInterface
        :return: uid
        """

        classname = to_track.__class__.__name__
        try:
            uid = f"{classname}_{to_track._id}"
        except AttributeError:
            # no id associated, is it a single class instance? (like operator)
            uid = classname

        if not isinstance(to_track, TrackingInterface):
            raise NotImplementedError(
                f"Something tried to register {classname}, but it"
                f"does not implement the necessary TrackingInterface!"
            )
        else:
            self.tracked[uid] = {
                "class": classname,
                "id": to_track._id,
                "reference": to_track,
            }
            logging.debug(
                f"Registered {classname} with ID {to_track._id}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

        return uid

    def unregister_by_uid(self, uid: str):
        try:
            result = self.tracked.pop(uid)
            logging.debug(
                f"Unregistered {result['class']} with ID {result['id']}",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
        except KeyError:
            logging.warning(
                f"Trying to unregister uid {uid}, but this uid is currently not tracked!",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

    def unregister_by_obj(self, to_untrack: TrackingInterface):
        uid = self._get_uid(to_untrack)
        self.unregister_by_uid(uid)

    def get(self, obj, attribute) -> Any:
        if isinstance(obj, str):
            uid = obj
        elif isinstance(obj, object):
            uid = self._get_uid(obj)
        try:
            return self.__env.now, self.tracked[uid]["reference"].get(attribute)
        except (KeyError, PermissionError) as e:
            if type(e) is KeyError:
                logging.error(
                    f"Trying to access {attribute} of uid {obj}, but this uid is currently not tracked!",
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )
                return None
            elif type(e) is PermissionError:
                logging.error(
                    f"{attribute} of uid {obj} is not exposed or does not exist!",
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )
                return None

    def dump(self, uid, exposed_only: bool = True) -> Optional[Tuple[float, dict]]:
        try:
            return self.__env.now, self.tracked[uid]["reference"].dump(exposed_only)
        except KeyError:
            logging.error(
                f"Trying to dump attributes of uid {uid}, but this uid is currently not tracked!",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )
            return None

    def list_tracked(self, classname) -> list:
        """
        List tracked uid's of the specific class requested

        :param classname: class type to list
        :return: list of uid
        """
        return [x for x, y in self.tracked.items() if y["class"] == classname]

    def _get_object(self, uid) -> Optional[TrackingInterface]:
        """
        It is discouraged to use this method extensively, rather use the get() and dump() methods that tracking exposes.

        :param uid: tracking-internal unique identifier of the object
        :return: object that implements TrackingInterface
        """
        try:
            return self.tracked[uid]["reference"]
        except KeyError:
            logging.error(
                f"Trying to access object at uid {uid}, but this uid is currently not tracked!",
                extra={"clazz": self.__class__.__name__, "oid": ""},
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
            uid = f"{classname}_{object._id}"
        except AttributeError:
            # no id associated, is it a single class instance? (like operator)
            uid = classname

        if uid not in self.tracked:
            logging.warning(
                f"Generated uid for object at uid {uid}, but this uid is currently not tracked!",
                extra={"clazz": self.__class__.__name__, "oid": ""},
            )

        return uid
