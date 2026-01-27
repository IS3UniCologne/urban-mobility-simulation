"""Interface for vehicles that support user and operator reservations."""

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
    def reserved_for_operator(self) -> bool:
        """Check if the vehicle is reserved for operator tasks."""

    @property
    @abstractmethod
    def is_reserved(self) -> bool:
        """Check if the vehicle is currently reserved."""

    @abstractmethod
    def reserve_for_user(self, user: "User") -> None:
        """Reserve the vehicle for a user.

        Parameters
        ----------
        user : User
            The user who wants to reserve the vehicle.

        Raises
        ------
        AlreadyReservedForUserError
            If the vehicle is already reserved for another user.
        AlreadyReservedForOperatorError
            If the vehicle is already reserved for operator tasks.
        """

    @abstractmethod
    def reserve_for_operator(self) -> None:
        """Reserve the vehicle for operator tasks.

        Raises
        ------
        AlreadyReservedForUserError
            If the vehicle is already reserved for a user.
        AlreadyReservedForOperatorError
            If the vehicle is already reserved for operator tasks.
        """

    @abstractmethod
    def release_reservation(self) -> None:
        """Release the current reservation."""
