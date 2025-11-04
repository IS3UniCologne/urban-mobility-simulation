"""UID manager for generating unique identifiers for simulation objects."""

from __future__ import annotations


class UidManager:
    """
    Manages UID generation for simulation objects.

    This class generates two different identifiers:
    1. An integer ID that is unique within the class type.
    2. A string UID that combines the class name and the integer ID and is truly unique across the entire simulation.
    """

    def __init__(self) -> None:
        self._uid_counters: dict[type, int] = {}

    def generate_uid(self, cls: type) -> tuple[int, str]:
        """
        Generate a unique identifier for the given class.

        Parameters
        ----------
        cls : type
            The class type for which to generate a UID.

        Returns
        -------
        tuple[int, str]
            A tuple containing an integer ID and a string UID.
        """
        if cls not in self._uid_counters:
            self._uid_counters[cls] = 0
        id = self._uid_counters[cls]
        uid = f"{cls.__name__}_{id}"
        self._uid_counters[cls] += 1
        return id, uid
