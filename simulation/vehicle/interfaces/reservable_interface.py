"""Interface for vehicles that support user and operator reservations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.vehicle.reservation import Reservation


class ReservableInterface(ABC):
    """Interface defining reservation capabilities for vehicles."""

    @property
    @abstractmethod
    def current_reservation(self) -> Reservation | None:
        """Active reservation.

        Returns
        -------
        Reservation or None
            Active reservation, or None if unreserved.
        """

    @property
    @abstractmethod
    def reserved_for_user(self) -> User | None:
        """User holding the reservation.

        Returns
        -------
        User or None
            User from the current reservation, or None if unreserved or operator-reserved.
        """

    @property
    @abstractmethod
    def is_reserved(self) -> bool:
        """True if vehicle has an active reservation."""

    @abstractmethod
    def reserve(self, requester: User | None = None) -> Reservation:
        """Reserve vehicle.

        Parameters
        ----------
        requester : User or None
            Reserving user, or None for operator reservations.

        Returns
        -------
        Reservation
            Yieldable reservation; yield ``reservation.ready_event`` to wait for availability.

        Raises
        ------
        AlreadyReservedError
            If the vehicle already has an active reservation.
        """

    @property
    @abstractmethod
    def is_in_use(self) -> bool:
        """True if vehicle has an active use."""

    @abstractmethod
    def acquire_use(self, reservation: Reservation, holder: User | None = None) -> None:
        """Convert current reservation into active use.

        Parameters
        ----------
        reservation : Reservation
            The reservation token obtained from ``reserve()``.
        holder : User or None
            User actively using the vehicle, or None for operator use.

        Raises
        ------
        InvalidReservationError
            If ``reservation`` does not match the vehicle's active reservation.
        """

    @abstractmethod
    def release_use(self) -> None:
        """Release active vehicle use."""

    @abstractmethod
    def cancel_queued_user_reservation(self, reason: str) -> bool:
        """Cancel a queued user reservation while vehicle is currently in use.

        Parameters
        ----------
        reason : str
            Human-readable cancellation reason for observability.

        Returns
        -------
        bool
            True if a queued user reservation was canceled, else False.
        """
