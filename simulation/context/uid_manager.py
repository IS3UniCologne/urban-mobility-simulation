"""UID manager for generating unique identifiers for simulation objects."""

from __future__ import annotations


class UidManager:
    """
    Manages UID generation for simulation objects.

    This class generates unique identifiers for simulation objects.
    """

    def __init__(self) -> None:
        self._uid_counters: dict[type, int] = {}

    def generate_uid(self, cls: type) -> str:
        """
        Generate a unique identifier for the given class.

        Parameters
        ----------
        cls : type
            The class type for which to generate a UID.

        Returns
        -------
        str
            A unique identifier in the format "ClassName_counter".
        """
        if cls not in self._uid_counters:
            self._uid_counters[cls] = 0
        uid = f"{cls.__name__}_{self._uid_counters[cls]}"
        self._uid_counters[cls] += 1
        return uid
