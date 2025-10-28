"""Module containing various enums used in the simulation."""

from __future__ import annotations

import sys
from enum import Enum, IntEnum

if sys.version_info >= (3, 11):
    from enum import StrEnum  # Python 3.11+
else:

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """
        StrEnum replacement for Python < 3.11.

        We can remove this once we drop support for Python 3.11.
        """


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
    MOVING_TO_PICK_UP = 4
    WAITING_FOR_VEHICLE = 5
    DRIVING = 6
    PAYING = 7
    FULFILLED = 8
    CANCELLED = 9  # TODO: This state seems unused
    MISSED = 10
    # ride hailing specifics
    REFUSED = 11
    # transit user specifics
    IN_TRANSPORT = 101
    MOVING_TO_DESTINATION = 102  # walk after last transit stop


# TODO: Have a state setter with checks for valid transitions ?
class VehicleState(Enum):
    """Vehicle states."""

    ### Generic vehicle states ###
    INITIALIZED = 0
    PARKING = 1
    DRIVING = 2
    RELOCATING = 3
    CHARGING = 4
    PRE_SERVICE = 5
    ONLINE = 6  # When the driver is online
    OFFLINE = 7  # When the driver is offline
    SOME_STATE = 1002
    RESERVED = 1001
    MOVING_TO_PICK_UP_POS = 1003

    ### Public transport vehicle states ###
    AT_TERMINAL_ORIGIN = 2001
    AT_TERMINAL_DESTINATION = 2002
    AT_STOP = 2003

    # bus specific
    EN_ROUTE_PLANNED = 2011
    EN_ROUTE_DETOUR = 2012

    UNKNOWN = 2999


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
