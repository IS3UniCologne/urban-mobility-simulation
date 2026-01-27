"""Mixin providing reservation functionality for vehicles."""

from typing import TYPE_CHECKING

from simulation.helper.exceptions import (
    AlreadyReservedForOperatorError,
    AlreadyReservedForUserError,
)
from simulation.vehicle.interfaces.reservable_interface import ReservableInterface

if TYPE_CHECKING:
    from logging import Logger

    from simulation.agent.user import User


class ReservableMixin(ReservableInterface):
    """Mixin providing user and operator reservation functionality for vehicles."""

    __slots__ = ()

    if TYPE_CHECKING:
        logger: Logger
        uid: str  # Vehicle UID for error messages

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._reserved_for_user: User | None = None
        self._reserved_for_operator: bool = False

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
    def reserved_for_operator(self) -> bool:
        """Check if the vehicle is reserved for operator tasks.

        Returns
        -------
        bool
            True if reserved for operator tasks, False otherwise.
        """
        return self._reserved_for_operator

    @property
    def is_reserved(self) -> bool:
        """Check if the vehicle is currently reserved.

        Returns
        -------
        bool
            True if the vehicle is reserved, False otherwise.
        """
        return self._reserved_for_user is not None or self._reserved_for_operator

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
        if self.is_reserved:
            if self._reserved_for_operator:
                self.logger.error("Vehicle is already reserved for operator tasks.")
                raise AlreadyReservedForOperatorError(vehicle_uid=self.uid)
            else:
                existing_user_uid = (
                    self._reserved_for_user.uid if self._reserved_for_user else "None"
                )
                self.logger.error(
                    "Vehicle is already reserved for user %s.", existing_user_uid
                )
                raise AlreadyReservedForUserError(
                    vehicle_uid=self.uid, user_uid=existing_user_uid
                )

        self._reserved_for_user = user
        self.logger.debug("Reserved for user %s.", user.uid)

    def reserve_for_operator(self) -> None:
        """Reserve the vehicle for operator tasks.

        Raises
        ------
        AlreadyReservedForUserError
            If the vehicle is already reserved for a user.
        AlreadyReservedForOperatorError
            If the vehicle is already reserved for operator tasks.
        """
        if self.is_reserved:
            if self._reserved_for_user is not None:
                self.logger.error(
                    "Vehicle is already reserved for user %s.",
                    self._reserved_for_user.uid,
                )
                raise AlreadyReservedForUserError(
                    vehicle_uid=self.uid, user_uid=self._reserved_for_user.uid
                )
            else:
                self.logger.error("Vehicle is already reserved for operator tasks.")
                raise AlreadyReservedForOperatorError(vehicle_uid=self.uid)

        self._reserved_for_operator = True
        self.logger.debug("Reserved for operator tasks.")

    def release_reservation(self) -> None:
        """Release the current reservation (user or operator)."""
        if self._reserved_for_user is not None:
            user_id = self._reserved_for_user.uid
            self._reserved_for_user = None
            self.logger.debug("Reservation released for user %s.", user_id)
        elif self._reserved_for_operator:
            self._reserved_for_operator = False
            self.logger.debug("Reservation released for operator tasks.")
