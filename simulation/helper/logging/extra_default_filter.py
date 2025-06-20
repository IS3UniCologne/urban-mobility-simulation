"""Logging filter that ensures 'uid' attribute is present in log records."""

import logging


class UidInjector(logging.Filter):
    """
    Logging filter that adds 'uid' attribute to log records.

    Parameters
    ----------
    filter_name : str
        The name of the filter.
    """

    def __init__(self, filter_name: str) -> None:
        """
        Initialize the UidInjector.

        Parameters
        ----------
        filter_name : str
            The name of the filter.
        """
        super().__init__(filter_name)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add 'uid' attribute to the log record if it is missing.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to filter.

        Returns
        -------
        bool
            Always returns True to allow the record to be logged.
        """
        if not hasattr(record, "uid"):
            record.uid = "Unknown"
        return True
