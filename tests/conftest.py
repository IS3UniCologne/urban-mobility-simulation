"""Fixtures shared by every test package."""

from __future__ import annotations

import pytest

from tests.datasets import ensure_datasets


@pytest.fixture(scope="session")
def datasets() -> None:
    """Build the datasets the test projects point at that are missing or out of date."""
    ensure_datasets()
