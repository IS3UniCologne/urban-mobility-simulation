import datetime
from typing import List, Optional
from beartype import beartype

from simpy import Environment

WEEKDAYS: List[str] = [
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

    def __init__(self, env: Environment) -> None:
        self._env = env

    def now(self) -> float:
        return self._env.now

    @beartype
    def seconds(self) -> int:
        return SimulationTimeConverter.seconds(self._env.now)

    @beartype
    def minutes(self) -> int:
        return SimulationTimeConverter.minutes(self._env.now)

    @beartype
    def hours(self) -> int:
        return SimulationTimeConverter.hours(self._env.now)

    @beartype
    def dayofweek(self) -> int:
        return SimulationTimeConverter.dayofweek(self._env.now)

    @beartype
    def dayofweek_as_str(self) -> str:
        return SimulationTimeConverter.dayofweek_as_str(self._env.now)

    @beartype
    def next_dayofweek_as_str(self) -> str:
        return SimulationTimeConverter.next_dayofweek_as_str(self._env.now)

    @beartype
    def last_dayofweek_as_str(self) -> str:
        return SimulationTimeConverter.last_dayofweek_as_str(self._env.now)

    @beartype
    def now_as_str(self, strf: str = "%H:%M:%S") -> str:
        return SimulationTimeConverter.as_str(self._env.now, strf)

    @beartype
    def now_as_time(self) -> datetime.time:
        return SimulationTimeConverter.as_time(self._env.now)

    @beartype
    def convert_to_day_of_week_bucket(self) -> bool:
        return SimulationTimeConverter.convert_to_day_of_week_bucket(self._env.now)


class SimulationTimeConverter:
    @staticmethod
    @beartype
    def seconds(time: float) -> int:
        return int((time - int(time)) * 60)

    @staticmethod
    @beartype
    def minutes(time: float) -> int:
        return int(time % 60)

    @staticmethod
    @beartype
    def hours(time: float) -> int:
        return int((time / 60) % 24)

    @staticmethod
    @beartype
    def days(time: float) -> int:
        return int(time / (24 * 60)) + 1

    @staticmethod
    @beartype
    def dayofweek(time: float) -> int:
        return int((time % (24 * 60 * 7)) / (24 * 60))

    @classmethod
    @beartype
    def dayofweek_as_str(cls, time: float) -> str:
        return WEEKDAYS[cls.dayofweek(time)]

    @classmethod
    @beartype
    def next_dayofweek_as_str(cls, time: float) -> str:
        return WEEKDAYS[(cls.dayofweek(time) + 1) % 7]

    @classmethod
    @beartype
    def last_dayofweek_as_str(cls, time: float) -> str:
        return WEEKDAYS[(cls.dayofweek(time) + 6) % 7]

    @classmethod
    @beartype
    def as_str(cls, time: float, strf: str = "%H:%M:%S") -> str:
        return cls.as_time(time).strftime(strf)

    @classmethod
    @beartype
    def as_time(cls, time: float) -> datetime.time:
        return datetime.time(cls.hours(time), cls.minutes(time), cls.seconds(time))

    @classmethod
    @beartype
    def as_datetime(cls, time: float) -> datetime.datetime:
        return datetime.datetime(
            2024,
            1,
            cls.days(time),
            cls.hours(time),
            cls.minutes(time),
            cls.seconds(time),
        )

    @staticmethod
    @beartype
    def duration_between(
        start: str, end: str, strf: str = "%H:%M:%S", end_next_day: Optional[bool] = None
    ) -> float:
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
    @beartype
    def convert_to_day_of_week_bucket(cls, time: float) -> bool:
        return cls.dayofweek(time) >= 5

    @staticmethod
    @beartype
    def convert_to_temporal_bucket(time: float, temporal_resolution: float) -> int:
        return (time % (24 * 60)) // (temporal_resolution * 60)


class SimulationVelocityConverter:
    @staticmethod
    @beartype
    def convert_kmh(velocity: float) -> float:
        return (velocity * 1000) / 60
