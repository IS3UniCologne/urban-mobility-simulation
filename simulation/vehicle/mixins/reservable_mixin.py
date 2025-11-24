"""Mixin providing reservation functionality for vehicles."""

from typing import TYPE_CHECKING

from simulation.vehicle.interfaces.reservable_interface import ReservableInterface

if TYPE_CHECKING:
    from logging import Logger

    from simulation.agent.user import User
    from simulation.helper.configuration.enums import VehicleState


class ReservableMixin(ReservableInterface):
    """Mixin providing user reservation functionality for vehicles."""

    __slots__ = ()

    if TYPE_CHECKING:
        logger: Logger
        state: VehicleState

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._reserved_for_user: User | None = None

    @property
    def reserved_for_user(self) -> "User | None":
        """Get the user who reserved this vehicle.

        Returns
        -------
        User | None
            The user who has reserved the vehicle, or None if not reserved.
        """
        return self._reserved_for_user

    @property
    def is_reserved(self) -> bool:
        """Check if the vehicle is currently reserved.

        Returns
        -------
        bool
            True if the vehicle is reserved, False otherwise.
        """
        return self._reserved_for_user is not None

    def reserve(self, user: "User") -> bool:
        """Reserve the vehicle for a user.

        Parameters
        ----------
        user : User
            The user who wants to reserve the vehicle.
        """
        if self.is_reserved:
            self.logger.debug(
                "Vehicle is already reserved for another user: %s.",
                self._reserved_for_user.uid if self._reserved_for_user else "None",
            )
            return False

        self._reserved_for_user = user
        self.logger.debug("Reserved to %s.", user.uid)
        return True

    def release_reservation(self) -> None:
        """Release the current reservation."""
        if self._reserved_for_user is not None:
            user_id = self._reserved_for_user.uid
            self._reserved_for_user = None
            self.logger.debug("Reservation released for user %s.", user_id)
