"""Mixin providing reservation functionality for vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.exceptions import (
    AlreadyReservedError,
    InvalidReservationError,
    ReservationStateError,
)
from simulation.helper.vehicle_states import VehicleStates
from simulation.vehicle.interfaces.reservable_interface import ReservableInterface
from simulation.vehicle.reservation import Reservation

if TYPE_CHECKING:
    from logging import Logger

    from simpy import Environment

    from simulation.agent.user import User
    from simulation.helper.state_machine import StateMachine
    from simulation.helper.vehicle_states import VehicleState


class ReservableMixin(ReservableInterface):
    """Mixin providing single-slot reservations for vehicles."""

    __slots__ = ()

    if TYPE_CHECKING:
        _env: Environment
        _state_machine: StateMachine[VehicleState]
        logger: Logger
        uid: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._reservation: Reservation | None = None
        self._is_in_use: bool = False

    @property
    def current_reservation(self) -> Reservation | None:
        """Active reservation.

        Returns
        -------
        Reservation or None
            Active reservation, or None if unreserved.
        """
        return self._reservation

    @property
    def reserved_for_user(self) -> User | None:
        """User holding the reservation.

        Returns
        -------
        User or None
            User from the current reservation, or None if unreserved or operator-reserved.
        """
        if self._reservation is not None and not self._reservation.is_operator:
            return self._reservation.requester
        return None

    @property
    def is_reserved(self) -> bool:
        """True if vehicle has an active reservation."""
        return self._reservation is not None

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
            If the vehicle already has an active reservation. Callers should check ``is_reserved``
            before attempting to reserve to avoid this.
        ReservationStateError
            If the vehicle is not in use and not in STANDBY — reserving in this state would
            leave the reservation permanently unfulfilled.
        """
        label = requester.uid if requester else "operator"

        if self._reservation is not None:
            raise AlreadyReservedError(vehicle_uid=self.uid, requester=label)

        reservation = Reservation(env=self._env, requester=requester)

        # Vehicle not in use - fulfill immediately
        if not self._is_in_use:
            if self.state is not VehicleStates.STANDBY:
                raise ReservationStateError(
                    f"Vehicle {self.uid}: cannot reserve vehicle not in use and not in STANDBY "
                    f"(state={self.state!r})",
                    vehicle_uid=self.uid,
                )
            self._reservation = reservation
            reservation.fulfill()
            self.logger.debug("Reserved for %s.", label)
            return reservation

        # Vehicle in use, queue reservation
        self._reservation = reservation
        self.logger.debug("Reservation for %s set as next (vehicle in use).", label)
        return reservation

    @property
    def is_in_use(self) -> bool:
        """True if vehicle has an active use."""
        return self._is_in_use

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
        if reservation is not self._reservation:
            raise InvalidReservationError(vehicle_uid=self.uid)

        self._is_in_use = True
        self._reservation = None

        self.logger.debug("Use acquired by %s.", holder.uid if holder else "operator")

    def release_use(self) -> None:
        """Release active vehicle use.

        Raises
        ------
        ReservationStateError
            If a queued reservation exists but the vehicle is not in STANDBY — this would
            leave the reservation permanently unfulfilled.
        """
        if not self._is_in_use:
            return

        self._is_in_use = False
        self.clear_predicted_state()  # type: ignore[attr-defined], this will be cleaner once we use components instead

        if self._reservation is not None:
            if self.state is not VehicleStates.STANDBY:
                raise ReservationStateError(
                    f"Vehicle {self.uid}: released use with pending reservation but state is "
                    f"{self.state!r} — reservation would be stuck",
                    vehicle_uid=self.uid,
                )
            self._reservation.fulfill()

        self.logger.debug("Use released.")
