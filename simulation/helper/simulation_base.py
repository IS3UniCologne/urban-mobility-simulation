"""Base class for simulation objects with UID assignment and logging capabilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.logging.uid_logger_adapter import UidLoggerAdapter
    from simulation.helper.types import SimId


class SimulationBase:
    """Base class for UID assignment and logging.

    UIDs are a combination of the class name and an incrementing integer.
    Each class gets its own logger for individual log level control.
    The class logger is wrapped in a UidLoggerAdapter to automatically include the UID
    in all log records without needing to specify it manually.
    """

    __slots__ = ("__weakref__", "_id", "_logger", "_uid")

    def __init__(self, sim: SimulationContext) -> None:
        # Initialize the unique identifier for the instance.
        cls = self.__class__
        self._id, self._uid = sim.uid_manager.generate_uid(cls)
        self._logger: UidLoggerAdapter = sim.log_manager.get_uid_logger(self._uid)

        # Register the instance with the UID manager for lookup.
        sim.uid_manager.register_object(self._uid, self)

    @property
    def id(self) -> int:
        """Return the integer ID for the instance.

        Warning: This ID is not globally unique across different classes.
        For a globally unique identifier, use the `uid` property instead.
        """
        return self._id

    @property
    def uid(self) -> SimId:
        """Return the unique identifier for the instance."""
        return self._uid

    @property
    def logger(self) -> UidLoggerAdapter:
        """Return the UID-specific logger for this instance with automatic context."""
        return self._logger

    def __str__(self) -> str:
        """Return the string representation of the instance."""
        return self.uid
