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


# ============================================================================
# Task Exceptions
# ============================================================================


class TaskAborted(Exception):
    """Raised to signal early task termination."""
