"""Reservation for vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simpy import Environment, Event

    from simulation.agent.user import User


class Reservation:
    """Yieldable reservation for vehicles.

    Wraps a SimPy event that is triggered when the vehicle becomes available.

    Parameters
    ----------
    env : Environment
        The SimPy environment.
    requester : User or None
        The user who requested the reservation, or None for operator
        reservations.
    """

    __slots__ = ("_ready_event", "_requester")

    def __init__(self, env: Environment, requester: User | None = None) -> None:
        self._requester = requester
        self._ready_event: Event = env.event()

    @property
    def requester(self) -> User | None:
        """Get the user who requested the reservation."""
        return self._requester

    @property
    def is_operator(self) -> bool:
        """Check if this is an operator reservation.

        Derived from ``requester`` being ``None``.
        """
        return self._requester is None

    @property
    def ready_event(self) -> Event:
        """Get the SimPy event to yield for vehicle availability."""
        return self._ready_event

    def fulfill(self) -> None:
        """Fulfill the reservation, signaling that the vehicle is available."""
        if not self._ready_event.triggered:
            self._ready_event.succeed()
