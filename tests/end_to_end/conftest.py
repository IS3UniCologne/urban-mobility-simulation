"""Fixtures for end-to-end tests."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _e2e_datasets(datasets: None) -> None:
    """Build the scenario datasets before any end-to-end test runs."""
