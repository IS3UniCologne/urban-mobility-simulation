"""Logger adapter that automatically adds UID context to log records."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import MutableMapping


class UidLoggerAdapter(logging.LoggerAdapter):  # type: ignore[type-arg]
    """
    Logger adapter that automatically adds UID to log records.

    This adapter ensures that the UID (which contains both class name and ID)
    is automatically included in all log records without requiring manual
    extra parameter specification. This also avoids the overhead of creating
    a new dictionary for every log call by pre-caching the extra dictionary.
    """

    __slots__ = ("_extra_uid",)

    def __init__(self, logger: logging.Logger, uid: str) -> None:
        """
        Initialize the adapter with a logger and UID.

        Parameters
        ----------
        logger : logging.Logger
            The base logger to wrap.
        uid : str
            The unique identifier to include in all log records.
        """
        uid_dict = {"uid": uid}
        super().__init__(logger, uid_dict)
        # Pre-cache the extra dict to avoid repeated creation
        self._extra_uid = uid_dict

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        """
        Process the logging call to add UID context.

        Uses pre-cached dictionaries and fast-path optimization for the
        most common case (no existing extra parameters).

        Parameters
        ----------
        msg : str
            The log message.
        kwargs : MutableMapping[str, Any]
            The keyword arguments from the logging call.

        Returns
        -------
        tuple[str, MutableMapping[str, Any]]
            The processed message and kwargs with UID added to extra.
        """
        if "extra" not in kwargs:
            # No additional context, use pre-cached extra
            kwargs["extra"] = self._extra_uid
            return msg, kwargs

        existing_extra = kwargs["extra"]
        kwargs["extra"] = {**existing_extra, **self._extra_uid}
        return msg, kwargs
