"""Lgging filter that injects the current simulation time from a SimPy environment into log records."""

import logging

import simpy


class SimulationContextFilter(logging.Filter):
    """
    Logging filter that injects the current simulation time from a SimPy environment into log records.

    Attributes
    ----------
    _env : simpy.Environment
        The SimPy environment providing the current simulation time.

    Methods
    -------
    filter(record: logging.LogRecord) -> bool
        Adds the current simulation time to the log record.
    """

    __slots__ = ("_env",)

    def __init__(self, filter_name: str, extra: simpy.Environment) -> None:
        super().__init__(filter_name)
        self._env: simpy.Environment = extra

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add the current simulation time to the log record.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to which the simulation time will be added.

        Returns
        -------
        bool
            Always returns True to allow the log record to be processed.
        """
        record.env_time = round(self._env.now, 2)
        return True
