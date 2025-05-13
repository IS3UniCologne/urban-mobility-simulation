from enum import Enum


class TemporalBucket(Enum):
    HOURLY_BUCKETS = 1
    TWO_HOURLY_BUCKETS = 2
    FOUR_HOURLY_BUCKETS = 4
    SIX_HOURLY_BUCKETS = 6
    EIGHT_HOURLY_BUCKETS = 8
    TWELVE_HOURLY_BUCKETS = 12


class DailyResolution(Enum):
    DAILY = 0
    WEEKDAY_WEEKEND = 1
    NONE = 2


class SpatialResolution(Enum):
    HEX_7 = 7
    HEX_8 = 8
    HEX_9 = 9


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
