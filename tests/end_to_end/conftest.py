"""Fixtures for end-to-end tests.

Builds the per-scenario synthetic datasets referenced by the configs under
``tests/configurations`` before any e2e test runs.
"""

from __future__ import annotations

import pytest

from tests.end_to_end.end_to_end_shared import build_e2e_datasets


@pytest.fixture(scope="session", autouse=True)
def e2e_datasets() -> None:
    """Generate every scenario dataset referenced by the e2e configs."""
    build_e2e_datasets()
