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

class Configuration:
    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> 'Configuration':
        """ Static access method. """
        if Configuration.__instance == None:
            Configuration(spatial_resolution = 7, temporal_resolution = 4)
        return Configuration.__instance

    @staticmethod
    def init(spatial_resolution, temporal_resolution, daily_resolution):
        """ Static access method. """
        if Configuration.__instance == None:
            Configuration(spatial_resolution, temporal_resolution, daily_resolution)
        return Configuration.__instance

    def __init__(self, spatial_resolution: int, temporal_resolution: int, daily_resolution: int):
        """ Virtually private constructor. """
        if Configuration.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            Configuration.__instance = self
            super(Configuration, self).__init__()

        self._spatial_resolution = SpatialResolution(spatial_resolution)
        self._temporal_resolution = TemporalBucket(temporal_resolution)
        self._daily_resolution = DailyResolution(daily_resolution)

    @property
    def spatial_resolution(self):
        return self._spatial_resolution

    @property
    def spatial_resolution_value(self):
        return self._spatial_resolution.value

    @property
    def temporal_resolution(self):
        return self._temporal_resolution

    @property
    def spatial_resolution_column(self):
        return f"hex_id_{self.spatial_resolution_value}"

    @property
    def daily_resolution(self):
        return self._daily_resolution
