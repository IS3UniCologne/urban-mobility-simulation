from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from simulation.helper.logging.log_manager import LogManager

if TYPE_CHECKING:
    from simulation.helper.logging.uid_logger_adapter import UidLoggerAdapter


class SimulationBase:
    """
    Base class for UID generation and logging.

    UIDs are a combination of the class name and an incrementing integer.
    Each class gets its own logger for individual log level control.
    """

    _uid_counters: ClassVar[dict[type, int]] = {}

    def __init__(self) -> None:
        # Initialize the unique identifier for the instance.
        cls = self.__class__
        if cls not in SimulationBase._uid_counters:
            SimulationBase._uid_counters[cls] = 0
        self._uid = f"{self.__class__.__name__}_{SimulationBase._uid_counters[cls]}"
        SimulationBase._uid_counters[cls] += 1

        self._logger: UidLoggerAdapter = LogManager.get_uid_logger(self._uid)

    @property
    def uid(self) -> str:
        """Return the unique identifier for the instance."""
        return self._uid

    @property
    def logger(self) -> UidLoggerAdapter:
        """Return the UID-specific logger for this instance with automatic context."""
        return self._logger

    def __str__(self) -> str:
        """Return the string representation of the instance."""
        return self.uid
