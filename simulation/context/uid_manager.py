"""UID manager for generating unique identifiers for simulation objects."""

from __future__ import annotations

import weakref
from typing import Any

from simulation.helper.types import SimId


class UidManager:
    """
    Manages UID generation for simulation objects.

    This class generates two different identifiers:
    1. An integer ID that is unique within the class type.
    2. A string UID that combines the class name and the integer ID and is truly unique across the entire simulation.
    """

    def __init__(self) -> None:
        self._uid_counters: dict[type, int] = {}
        self._uid_registry: weakref.WeakValueDictionary[SimId, Any] = (
            weakref.WeakValueDictionary()
        )

    def generate_uid(self, cls: type) -> tuple[int, SimId]:
        """
        Generate a unique identifier for the given class.

        Parameters
        ----------
        cls : type
            The class type for which to generate a UID.

        Returns
        -------
        tuple[int, SimId]
            A tuple containing an integer ID and a SimId UID.
        """
        if cls not in self._uid_counters:
            self._uid_counters[cls] = 0
        id = self._uid_counters[cls]
        uid = f"{cls.__name__}_{id}"
        self._uid_counters[cls] += 1
        return id, SimId(uid)

    def register_object(self, uid: SimId, obj: object) -> None:
        """
        Register an object with its UID for lookup.

        Uses weak references to avoid keeping objects alive unnecessarily.

        Parameters
        ----------
        uid : SimId
            The unique identifier.
        obj : Any
            The object to register.
        """
        self._uid_registry[uid] = obj

    def get_by_uid(self, uid: SimId) -> object | None:
        """
        Get an object by its UID.

        Parameters
        ----------
        uid : SimId
            The unique identifier to look up.

        Returns
        -------
        Any or None
            The registered object, or None if not found or already garbage collected.
        """
        return self._uid_registry.get(uid)
