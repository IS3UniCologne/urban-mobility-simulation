"""Logging filter that injects the current simulation time from a SimPy environment into log records."""

import logging

import simpy


class EnvTimeInjector(logging.Filter):
    """
    Logging filter that injects the current simulation time from a SimPy environment into log records.

    Parameters
    ----------
    filter_name : str
        Filter name.
    env : simpy.Environment
        SimPy environment providing the current simulation time.
    """

    __slots__ = ("_env",)

    def __init__(self, filter_name: str, env: simpy.Environment) -> None:
        super().__init__(filter_name)
        self._env: simpy.Environment = env

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add the current simulation time to the log record.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to annotate with the simulation time.

        Returns
        -------
        bool
            Always True, so the record is processed.
        """
        # This is faster than rounding, rounding errors should not be an issue
        record.env_time = int(self._env.now * 100) / 100
        return True
