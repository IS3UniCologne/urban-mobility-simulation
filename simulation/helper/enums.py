"""Module containing various enums used in the simulation."""

from __future__ import annotations

from enum import Enum, IntEnum, StrEnum


class TemporalResolution(IntEnum):
    """Temporal resolution buckets in hours."""

    HOURLY_BUCKETS = 1
    TWO_HOURLY_BUCKETS = 2
    FOUR_HOURLY_BUCKETS = 4
    SIX_HOURLY_BUCKETS = 6
    EIGHT_HOURLY_BUCKETS = 8
    TWELVE_HOURLY_BUCKETS = 12

    @property
    def column_name(self) -> str:
        """Get the column name for this temporal resolution."""
        if self == TemporalResolution.HOURLY_BUCKETS:
            return "hour_of_day"
        return f"time_bucket_{self.value}h"


class DailyResolution(StrEnum):
    """Daily resolution for demand data."""

    DAILY = "daily"
    WEEKDAY_WEEKEND = "weekday_weekend"
    NONE = "none"

    @property
    def day_of_week_column_name(self) -> str:
        """
        Get the day classification column name.

        Returns
        -------
        str
            Column name for day classification in the data
        """
        # TODO: Is this correct ? Seems a bit odd.
        return "is_holiday"


class SpatialResolution(IntEnum):
    """
    H3 spatial resolution levels.

    Higher values mean smaller hexagons.
    """

    HEX_7 = 7
    HEX_8 = 8
    HEX_9 = 9

    @property
    def origin_column_name(self) -> str:
        """Get the origin column name for this spatial resolution."""
        return f"h3_start_{self.value}"

    @property
    def destination_column_name(self) -> str:
        """Get the destination column name for this spatial resolution."""
        return f"h3_end_{self.value}"

    @property
    def origin_destination_columns(self) -> tuple[str, str]:
        """Get both origin and destination column names for this spatial resolution."""
        return self.origin_column_name, self.destination_column_name

    @property
    def column_name(self) -> str:
        """Returns the column name for the spatial resolution. E.g. 'hex_id_7'."""
        return f"hex_id_{self.value}"


class ModeChoiceStrategy(StrEnum):
    """Mode choice strategies for selecting transport alternatives."""

    RANDOM = "Random"
    SUBSTITUTION_AWARE = "SubstitutionAware"
    NO_SUBSTITUTION = "NoSubstitution"


class VehicleType(StrEnum):
    """Vehicle types, e.g. car, bike, scooter."""

    CAR = "Car"
    SCOOTER = "Scooter"
    KICK_SCOOTER = "KickScooter"
    BIKE = "Bike"
    BUS = "Bus"


class AutonomyType(StrEnum):
    """Vehicle autonomy, e.g. human-driven or autonomous."""

    HUMAN_DRIVEN = "HumanDriven"
    AUTONOMOUS = "Autonomous"


class PropulsionType(StrEnum):
    """Vehicle propulsion types."""

    BATTERY_ELECTRIC = "BatteryElectric"
    INTERNAL_COMBUSTION = "InternalCombustion"
    HUMAN_POWERED = "HumanPowered"  # E.g. bike


class UserState(Enum):
    """User states."""

    INITIALIZED = 0
    SEARCHING_TRANSPORT_ALTERNATIVES = 1
    SELECTING_TRANSPORT_ALTERNATIVES = 2
    AWAITING_ALLOCATION = 3
    WAITING_FOR_VEHICLE = 4
    DRIVING = 5
    PAYING = 6
    FULFILLED = 7
    CANCELLED = 8  # TODO: This state seems unused
    MISSED = 9
    # ride hailing specific
    REFUSED = 11
    MOVING_TO_PICK_UP = 12
    # shared mobility specific
    MOVING_TO_VEHICLE = 20
    # transit user specific
    MOVING_TO_TRANSPORT_STOP = 30
    IN_TRANSPORT = 31
    MOVING_TO_DESTINATION = 32  # walk after last transit stop
    WAITING_FOR_TRANSPORT = 33


# TODO: Do we need both withdrawn and missed? If so we should clarify the difference.
class TransactionState(StrEnum):
    """Transaction states."""

    FULFILLED = "Fulfilled"
    MISSED = "Missed"
    WITHDRAWN = "Withdrawn"


class OperatorMode(StrEnum):
    """Operator modes for different types of services."""

    # TODO: We probably should standardize these names across the codebase.
    RIDE_HAILING = "Ridehailing"
    SHARED_MOBILITY = "SharedMobility"
    PUBLIC_TRANSPORT = "PublicTransport"
