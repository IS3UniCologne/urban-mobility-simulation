"""Interface for vehicles that support user reservations."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User


class ReservableInterface(ABC):
    """Interface defining reservation capabilities for vehicles."""

    @property
    @abstractmethod
    def reserved_for_user(self) -> "User | None":
        """Get the user who reserved this vehicle."""

    @property
    @abstractmethod
    def is_reserved(self) -> bool:
        """Check if the vehicle is currently reserved."""

    @abstractmethod
    def reserve(self, user: "User") -> bool:
        """Reserve the vehicle for a user."""

    @abstractmethod
    def release_reservation(self) -> None:
        """Release the current reservation."""
