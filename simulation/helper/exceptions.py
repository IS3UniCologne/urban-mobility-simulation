"""Custom exceptions."""


# ============================================================================
# Vehicle Exceptions
# ============================================================================


class VehicleError(Exception):
    """Base class for all vehicle-related exceptions."""


class VehicleReservationError(VehicleError):
    """Base exception for vehicle reservation errors."""

    def __init__(self, message: str, vehicle_uid: str | None = None) -> None:
        self.vehicle_uid = vehicle_uid
        super().__init__(message)


class AlreadyReservedForUserError(VehicleReservationError):
    """Raised when attempting to reserve a vehicle already reserved for a user."""

    def __init__(self, vehicle_uid: str, user_uid: str) -> None:
        self.user_uid = user_uid
        super().__init__(
            f"Vehicle {vehicle_uid} is already reserved for user {user_uid}",
            vehicle_uid=vehicle_uid,
        )


class AlreadyReservedForOperatorError(VehicleReservationError):
    """Raised when attempting to reserve a vehicle already reserved for operator tasks."""

    def __init__(self, vehicle_uid: str) -> None:
        super().__init__(
            f"Vehicle {vehicle_uid} is already reserved for operator tasks",
            vehicle_uid=vehicle_uid,
        )


class PublicTransitVehicleException(VehicleError):
    """Base exception for public transit vehicle errors."""


class PublicTransitVehicleFull(PublicTransitVehicleException):
    """Raised when a public transit vehicle is at capacity."""


# ============================================================================
# Fleet Exceptions
# ============================================================================


class VehicleFleetError(Exception):
    """Base class for all vehicle fleet-related exceptions."""


# ============================================================================
# State Machine Exceptions
# ============================================================================


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


# ============================================================================
# Infrastructure Exceptions
# ============================================================================


class AmbiguousTripException(Exception):
    """Raised when a trip cannot be uniquely identified in the timetable."""


# ============================================================================
# Market/Auction Exceptions
# ============================================================================


class BidMalformedException(Exception):
    """Raised when a bid is malformed or invalid."""


class AuctionClosedException(Exception):
    """Raised when attempting to interact with a closed auction."""
