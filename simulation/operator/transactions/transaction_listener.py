"""
Base class for transaction listeners.

Defines the TransactionListener interface for listening to new transactions.
"""

from .transaction import Transaction


class TransactionListener:
    """
    Base class for transaction listeners.

    Subclass this and override `on_transaction` to listen for new transactions.

    Methods
    -------
    on_transaction(transaction: Transaction) -> None
        Called when a new transaction is added.
    """

    def on_transaction(self, transaction: Transaction) -> None:
        """
        Listen for a new transaction.

        Parameters
        ----------
        transaction : Transaction
            The transaction that was added.
        """
        pass
