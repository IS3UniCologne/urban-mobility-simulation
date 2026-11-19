"""Unit tests for the UID logger adapter."""

from __future__ import annotations

import logging

import pytest

from simulation.helper.logging.uid_logger_adapter import UidLoggerAdapter
from simulation.helper.types import SimId

pytestmark = pytest.mark.unit


def test_debug_record_names_its_caller(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("uid_logger_adapter_test")
    adapter = UidLoggerAdapter(logger, SimId("User_1"))

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        adapter.debug("Received %s alternatives", 3)

    (record,) = caplog.records
    assert record.funcName == "test_debug_record_names_its_caller"
    assert record.getMessage() == "Received 3 alternatives"
    assert record.uid == "User_1"
