"""Exclusive use of a vehicle."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User


class VehicleUse:
    """Exclusive use of a vehicle.

    Represents the period during which a user or operator has exclusive access to a vehicle.

    Parameters
    ----------
    holder : User or None
        The user who holds exclusive use, or None for operator use.
    """

    __slots__ = ("_holder",)

    def __init__(self, holder: User | None = None) -> None:
        self._holder = holder

    @property
    def holder(self) -> User | None:
        """Get the user who holds exclusive use."""
        return self._holder

    @property
    def is_operator(self) -> bool:
        """Check if this use is for operator tasks.

        Derived from ``holder`` being ``None``.
        """
        return self._holder is None
