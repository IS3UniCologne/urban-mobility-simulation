"""
Base class for OperatorLogEntry listeners.

Defines the OperatorLogEntryListener interface for listening to new operator log entries.
"""

from .operator_log_entry import OperatorLogEntry


class OperatorLogEntryListener:
    """
    Base class for listeners of `OperatorLogEntry` events.

    Subclass this and override `on_transaction` to listen for new operator log entries.
    """

    def on_transaction(self, transaction: OperatorLogEntry) -> None:
        """
        Listen for a new OperatorLogEntry.

        Parameters
        ----------
        transaction : OperatorLogEntry
            The operator log entry that was added.
        """
        pass
