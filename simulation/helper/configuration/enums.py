from enum import Enum, IntEnum

try:
    from enum import StrEnum  # Python 3.11+
except ImportError:

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
    def column_names(self) -> tuple[str, str]:
        """Get both origin and destination column names for this spatial resolution."""
        return self.origin_column_name, self.destination_column_name


class ModeChoiceStrategy(Enum):
    RANDOM = 0
    SUBSTITUTION_AWARE = 1
    NO_SUBSTITUTION = 2


class PopulationType(Enum):
    CLUSTER_0 = 0
    CLUSTER_1 = 1
    CLUSTER_2 = 2
    CLUSTER_3 = 3
    PRICE_SENSITIVE = 4
    CONVENIENCE_SEEKER = 5


class VehicleMode(Enum):
    Car = 0
    Scooter = 1
    KickScooter = 2
    Bike = 3
    Bus = 4


class UserState(Enum):
    INITIALIZED = 0
    SEARCHING_TRANSPORT_ALTERNATIVES = 1
    SELECTING_TRANSPORT_ALTERNATIVES = 2
    ALLOCATING_VEHICLE = 3
    MOVING_TO_PICK_UP_POS = 4
    WAITING_FOR_VEHICLE = 5
    DRIVING = 6
    PAYING = 7
    FULFILLED = 8
    CANCELLED = 9
    MISSED = 10
    # ride hailing specifics
    REFUSED = 11
    # transit user specifics
    IN_TRANSPORT = 101
    MOVING_TO_DESTINATION = 102  # walk after last transit stop


class VehicleState(Enum):
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


class TransactionState(StrEnum):
    FULFILLED = "Fulfilled"
    MISSED = "Missed"
