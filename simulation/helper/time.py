import datetime

from simpy import Environment

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class SimulationTime:
    """
    Implements easy access to simpy's environment time.
    While simpy's time is unitless, we assume it to be minutes.
    """

    __slots__ = ("_env",)

    def __init__(self, env: Environment):  # noqa: ANN204
        self._env = env

    def now(self):  # noqa: ANN201
        return self._env.now

    def seconds(self):  # noqa: ANN201
        return SimulationTimeConverter.seconds(self._env.now)

    def minutes(self):  # noqa: ANN201
        return SimulationTimeConverter.minutes(self._env.now)

    def hours(self):  # noqa: ANN201
        return SimulationTimeConverter.hours(self._env.now)

    def dayofweek(self):  # noqa: ANN201
        return SimulationTimeConverter.dayofweek(self._env.now)

    def dayofweek_as_str(self) -> str:
        return SimulationTimeConverter.dayofweek_as_str(self._env.now)

    def next_dayofweek_as_str(self) -> str:
        return SimulationTimeConverter.next_dayofweek_as_str(self._env.now)

    def last_dayofweek_as_str(self) -> str:
        return SimulationTimeConverter.last_dayofweek_as_str(self._env.now)

    def now_as_str(self, strf: str = "%H:%M:%S"):  # noqa: ANN201
        return SimulationTimeConverter.as_str(self._env.now, strf)

    def now_as_time(self):  # noqa: ANN201
        return SimulationTimeConverter.as_time(self._env.now)

    def convert_to_day_of_week_bucket(self):  # noqa: ANN201
        return


class SimulationTimeConverter:
    @staticmethod
    def seconds(time: float):  # noqa: ANN205
        # seconds are not well defined, but it may happen that a time step is < 1 (minutes)
        return int((time - int(time)) * 60)

    @staticmethod
    def minutes(time: float):  # noqa: ANN205
        return int(time % 60)

    @staticmethod
    def hours(time: float):  # noqa: ANN205
        return int((time / 60) % 24)

    @staticmethod
    def days(time: float):  # noqa: ANN205
        return int(time / (24 * 60)) + 1

    @staticmethod
    def dayofweek(time: float):  # noqa: ANN205
        return int((time % (24 * 60 * 7)) / (24 * 60))

    @classmethod
    def dayofweek_as_str(cls, time: float) -> str:
        return WEEKDAYS[cls.dayofweek(time)]

    @classmethod
    def next_dayofweek_as_str(cls, time: float) -> str:
        return WEEKDAYS[(cls.dayofweek(time) + 1) % 7]

    @classmethod
    def last_dayofweek_as_str(cls, time: float) -> str:
        return WEEKDAYS[
            (cls.dayofweek(time) + 6) % 7
        ]  # add 6 instead of subtracting 1 and let modulo do the work

    @classmethod
    def as_str(cls, time: float, strf: str = "%H:%M:%S"):  # noqa: ANN206
        return cls.as_time(time).strftime(strf)

    @classmethod
    def as_time(cls, time: float):  # noqa: ANN206
        return datetime.time(cls.hours(time), cls.minutes(time), cls.seconds(time))

    @classmethod
    def as_datetime(cls, time: float):  # noqa: ANN206
        # ATTENTION:
        # 1. we use some month where the first day is a monday, this does not align with seasons or anything
        # 2. simulation times of more than one month are not well defined
        return datetime.datetime(
            2024,
            1,
            cls.days(time),
            cls.hours(time),
            cls.minutes(time),
            cls.seconds(time),
        )

    @staticmethod
    def duration_between(  # noqa: ANN205
        start: str,
        end: str,
        strf: str = "%H:%M:%S",
        end_next_day=None,  # noqa: ANN001
    ):
        """
        Gives the duration between two timestamps in minutes.
        Must be start <= end for end_next_day = False

        :param end_next_day: bool/None
        :param start: strf-formatted timestamp
        :param end: strf-formatted timestamp
        :param strf: strf formatting
        :return: float - minutes
        """
        # try to infer end_next_day if not explicitly given
        if end_next_day is None:
            end_next_day = end < start

        if not end_next_day:
            return (
                datetime.datetime.strptime(end, strf)
                - datetime.datetime.strptime(start, strf)
            ).total_seconds() / 60
        else:
            return (
                datetime.datetime.strptime(end, strf)
                + datetime.timedelta(days=1)
                - datetime.datetime.strptime(start, strf)
            ).total_seconds() / 60

    @classmethod
    def convert_to_day_of_week_bucket(cls, time: float):  # noqa: ANN206
        if cls.dayofweek(time) < 5:
            return False  # Non_Working_Day? No => weekday
        else:
            return True  # Non_Working_Day? Yes (i.e., holidays, weekends)

    @staticmethod
    def convert_to_temporal_bucket(time: float, temporal_resolution):  # noqa: ANN001, ANN205
        return (time % (24 * 60)) // (
            temporal_resolution * 60
        )  # Reduce to one day, then get day of week


class SimulationVelocityConverter:
    # Convert the velocity of kilometer/hour to simulation velocity of meter/minute
    @staticmethod
    def convert_kmh(velocity: float):  # noqa: ANN205
        return (velocity * 1000) / 60
