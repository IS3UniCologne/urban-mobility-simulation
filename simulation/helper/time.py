"""Simulation time access and conversion helpers."""

import datetime

from simpy import Environment

from simulation.helper.types import SimTime

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 1440
HOURS_PER_DAY = 24  # used for price schedule


class SimulationTime:
    """
    Provide easy access to simpy's environment time.

    While simpy's time is unitless, we assume it to be minutes.

    Parameters
    ----------
    env : Environment
        SimPy environment providing the current simulation time.
    """

    __slots__ = ("_env",)

    def __init__(self, env: Environment) -> None:
        self._env = env

    def now(self) -> SimTime:
        """Return the current simulation time in minutes."""
        return self._env.now

    def seconds(self) -> int:
        """Return the seconds component of the current time."""
        return SimulationTimeConverter.seconds(self._env.now)

    def minutes(self) -> int:
        """Return the minutes component of the current time."""
        return SimulationTimeConverter.minutes(self._env.now)

    def hours(self) -> int:
        """Return the hours component of the current time."""
        return SimulationTimeConverter.hours(self._env.now)

    def dayofweek(self) -> int:
        """Return the current day of week as an integer (0 = Monday)."""
        return SimulationTimeConverter.dayofweek(self._env.now)

    def dayofweek_as_str(self) -> str:
        """Return the current day of week as a string."""
        return SimulationTimeConverter.dayofweek_as_str(self._env.now)

    def next_dayofweek_as_str(self) -> str:
        """Return the next day of week as a string."""
        return SimulationTimeConverter.next_dayofweek_as_str(self._env.now)

    def last_dayofweek_as_str(self) -> str:
        """Return the previous day of week as a string."""
        return SimulationTimeConverter.last_dayofweek_as_str(self._env.now)

    def now_as_str(self, strf: str = "%H:%M:%S") -> str:
        """Return the current time formatted with strf. Default format is HH:MM:SS."""
        return SimulationTimeConverter.as_str(self._env.now, strf)

    def now_as_time(self) -> datetime.time:
        """Return the current time as a datetime.time."""
        return SimulationTimeConverter.as_time(self._env.now)


class SimulationTimeConverter:
    """Convert simulation time (minutes) into calendar components."""

    @staticmethod
    def seconds(time: float) -> int:
        """Return the seconds component of a simulation time."""
        # seconds are not well defined, but it may happen that a time step is < 1 (minutes)
        return int((time - int(time)) * 60)

    @staticmethod
    def minutes(time: float) -> int:
        """Return the minutes component of a simulation time."""
        return int(time % 60)

    @staticmethod
    def hours(time: float) -> int:
        """Return the hour of day (0-23) for a simulation time."""
        return int((time / 60) % 24)

    @staticmethod
    def hour_of_day(time: float) -> int:
        """Return the hour of day for a simulation time."""
        return int((time % 1440 - time % 60) / 60)

    @staticmethod
    def days(time: float) -> int:
        """Return the 1-indexed day number for a simulation time."""
        return int(time / (24 * 60)) + 1

    @staticmethod
    def dayofweek(time: float) -> int:
        """Return the day of week (0 = Monday) for a simulation time."""
        return int((time % (24 * 60 * 7)) / (24 * 60))

    @classmethod
    def dayofweek_as_str(cls, time: float) -> str:
        """Return the day of week name for a simulation time."""
        return WEEKDAYS[cls.dayofweek(time)]

    @classmethod
    def next_dayofweek_as_str(cls, time: float) -> str:
        """Return the next day's name for a simulation time."""
        return WEEKDAYS[(cls.dayofweek(time) + 1) % 7]

    @classmethod
    def last_dayofweek_as_str(cls, time: float) -> str:
        """Return the previous day's name for a simulation time."""
        return WEEKDAYS[
            (cls.dayofweek(time) + 6) % 7
        ]  # add 6 instead of subtracting 1 and let modulo do the work

    @classmethod
    def as_str(cls, time: float, strf: str = "%H:%M:%S") -> str:
        """Return a simulation time formatted with strf."""
        return cls.as_time(time).strftime(strf)

    @classmethod
    def as_time(cls, time: float) -> datetime.time:
        """Return a simulation time as a datetime.time."""
        return datetime.time(cls.hours(time), cls.minutes(time), cls.seconds(time))

    @classmethod
    def as_datetime(cls, time: float) -> datetime.datetime:
        """Return a simulation time as a datetime.datetime."""
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
    def duration_between(
        start: str, end: str, strf: str = "%H:%M:%S", end_next_day: bool | None = None
    ) -> float:
        """
        Give the duration in minutes between two timestamps.

        Must satisfy start <= end when end_next_day is False.

        Parameters
        ----------
        start : str
            strf-formatted start timestamp.
        end : str
            strf-formatted end timestamp.
        strf : str
            strftime format string.
        end_next_day : bool or None
            Whether end falls on the next day. If None, inferred from start and end.

        Returns
        -------
        float
            Duration in minutes.
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
    def convert_to_day_of_week_bucket(cls, time: float) -> bool:
        """Return whether a simulation time falls on a non-working day."""
        if cls.dayofweek(time) < 5:
            return False  # Non_Working_Day? No => weekday
        else:
            return True  # Non_Working_Day? Yes (i.e., holidays, weekends)

    @staticmethod
    def convert_to_temporal_bucket(time: float, temporal_resolution: int) -> float:
        """Return the temporal bucket index for a simulation time."""
        return (time % (24 * 60)) // (
            temporal_resolution * 60
        )  # Reduce to one day, then get day of week


class SimulationVelocityConverter:
    """Convert velocities to different units."""

    # TODO: A class for this seems overkill.
    # Convert the velocity of kilometer/hour to simulation velocity of meter/minute
    @staticmethod
    def kmh_to_meters_per_minute(velocity: float) -> float:
        """Convert velocity from kilometers per hour to meters per minute.

        Parameters
        ----------
        velocity : float
            Velocity in kilometers per hour.

        Returns
        -------
        float
            Velocity in meters per minute.
        """
        return (velocity * 1000) / 60
