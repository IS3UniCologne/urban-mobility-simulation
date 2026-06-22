"""Logging filter that ensures 'uid' attribute is present in log records."""

import logging


class UidInjector(logging.Filter):
    """
    Logging filter that adds 'uid' attribute to log records.

    Parameters
    ----------
    filter_name : str
        Filter name.
    """

    def __init__(self, filter_name: str) -> None:
        super().__init__(filter_name)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add 'uid' attribute to the log record if it is missing.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to filter.

        Returns
        -------
        bool
            Always True, so the record is logged.
        """
        if not hasattr(record, "uid"):
            record.uid = record.name
        return True
