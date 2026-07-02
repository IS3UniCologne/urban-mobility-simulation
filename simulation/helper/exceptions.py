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


class AlreadyReservedError(VehicleReservationError):
    """Raised when attempting to reserve an already-reserved vehicle."""

    def __init__(self, vehicle_uid: str, requester: str) -> None:
        super().__init__(
            f"Vehicle {vehicle_uid} already reserved; cannot reserve for {requester}.",
            vehicle_uid=vehicle_uid,
        )


class InvalidReservationError(VehicleReservationError):
    """Raised when the reservation passed to acquire_use does not match the vehicle's active reservation."""

    def __init__(self, vehicle_uid: str) -> None:
        super().__init__(
            f"Reservation mismatch on vehicle {vehicle_uid}: caller does not hold the active reservation.",
            vehicle_uid=vehicle_uid,
        )


class ReservationCanceledError(VehicleReservationError):
    """Raised when a reservation was canceled before it could be consumed."""

    def __init__(self, vehicle_uid: str, reason: str | None = None) -> None:
        detail = f"Reason: {reason}." if reason else ""
        super().__init__(
            f"Reservation canceled on vehicle {vehicle_uid}. {detail}",
            vehicle_uid=vehicle_uid,
        )


class ReservationStateError(VehicleReservationError):
    """Raised when a reservation operation is attempted in an invalid vehicle state."""


class EnergyDepletedError(VehicleError):
    """Raised when a vehicle's energy is depleted during travel."""


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


class StopNotFoundError(Exception):
    """Raised when a stop cannot be located within a route."""


class TimetableNotImportedError(Exception):
    """Raised when timetable data is accessed before being imported."""


class HexagonNotFoundError(Exception):
    """Raised when a region id has no hexagon in the geodesic environment."""


# ============================================================================
# Market/Auction Exceptions
# ============================================================================


class BidMalformedException(Exception):
    """Raised when a bid is malformed or invalid."""


class AuctionClosedException(Exception):
    """Raised when attempting to interact with a closed auction."""


# ============================================================================
# Vehicle Task Exceptions
# ============================================================================


class TaskAborted(Exception):
    """Raised to signal early task termination."""


# ============================================================================
# General Exceptions
# ============================================================================


class MissingDependencyError(Exception):
    """Raised when an optional dependency required for a feature is not installed."""
