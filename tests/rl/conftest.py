"""Fixtures for the reinforcement learning tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts._cli.orchestrators import new_project
from scripts._cli.paths import REPO_ROOT
from tests.rl import HORIZON

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from rl.env import UmosimEnv
    from rl.problem import Problem

# Built for the balanced test projects under tests/configurations
_DATASET = "e2e_balanced"


@pytest.fixture(scope="session")
def admission_project(datasets: None, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold the admission starter onto a test dataset, as ``umosim demo`` does onto its own.

    The tests then run the project a user gets instead of a copy of it.
    """
    root = tmp_path_factory.mktemp("admission")
    link = root / "data" / "datasets" / _DATASET
    link.parent.mkdir(parents=True)
    link.symlink_to(
        REPO_ROOT / "data" / "datasets" / _DATASET, target_is_directory=True
    )
    return new_project("admission", _DATASET, operators=["admission"], root=root)


@pytest.fixture
def make_env(admission_project: Path) -> Iterator[Callable[..., UmosimEnv]]:
    """Build environments over the admission project with a short horizon.

    Every environment is closed after the test.
    A failing assert then leaks no waiting simulation and no log files.
    """
    # Local so the unit tests still collect without the rl extra
    from rl.env import UmosimEnv

    envs: list[UmosimEnv] = []

    def make(problem: Problem) -> UmosimEnv:
        env = UmosimEnv(admission_project, problem, horizon_min=HORIZON)
        envs.append(env)
        return env

    yield make
    for env in envs:
        env.close()
