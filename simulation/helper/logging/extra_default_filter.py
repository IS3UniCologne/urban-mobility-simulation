"""Logging filter that ensures default 'clazz' and 'oid' attributes are present in log records."""

import logging


class ExtraDefaultFilter(logging.Filter):
    """
    Logging filter that adds default 'clazz' and 'oid' attributes to log records.

    Parameters
    ----------
    filter_name : str
        The name of the filter.
    """

    def __init__(self, filter_name: str) -> None:
        """
        Initialize the ExtraDefaultFilter.

        Parameters
        ----------
        filter_name : str
            The name of the filter.
        """
        super().__init__(filter_name)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add default 'clazz' and 'oid' attributes to the log record if they are missing.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to filter.

        Returns
        -------
        bool
            Always returns True to allow the record to be logged.
        """
        if not hasattr(record, "clazz"):
            record.clazz = "Unknown"

        if not hasattr(record, "oid"):
            record.oid = "-"
        return True
