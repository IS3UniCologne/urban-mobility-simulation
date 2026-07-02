"""Cleanup helpers.

These are just convenience functions for common cleanup tasks during development.

Use at your own risk :)
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from scripts._cli.orchestrators import DEMO_DATASET, DEMO_PROJECT_NAMES
from scripts._cli.paths import REPO_ROOT

if TYPE_CHECKING:
    from pathlib import Path

TEST_DATASETS = ("e2e_saturated", "e2e_balanced", "e2e_wellsupplied")


def _ensure_source_checkout(root: Path) -> None:
    """Refuse to run if ``root`` is not a umosim source checkout.

    Raises
    ------
    RuntimeError
        When ``root`` lacks ``pyproject.toml``.
    """
    if not (root / "pyproject.toml").exists():
        raise RuntimeError(
            f"Refusing to run cleanup: {root} is not a umosim source checkout "
            f"(no pyproject.toml); clean-* only works from a cloned repository."
        )


def clean_demos(root: Path = REPO_ROOT) -> list[Path]:
    """Remove demo projects and demo/test datasets."""
    _ensure_source_checkout(root)
    removed: list[Path] = []

    project_targets = [
        root / "data" / "projects" / name for name in DEMO_PROJECT_NAMES.values()
    ]
    dataset_targets = [
        root / "data" / "datasets" / DEMO_DATASET,
        *(root / "data" / "datasets" / name for name in TEST_DATASETS),
    ]

    for path in project_targets + dataset_targets:
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed {path.relative_to(root)}")
            removed.append(path)

    print(f"Removed {len(removed)} demo/test artifact(s)")
    return removed


def clean_logs(root: Path = REPO_ROOT, keep: int = 10) -> tuple[int, int]:
    """Prune old log files under ``data/output/{logs,metrics_logs}``."""
    if keep < 0:
        raise ValueError(f"keep must be non-negative, got {keep}")
    _ensure_source_checkout(root)

    output_dir = root / "data" / "output"
    logs_removed = _prune_dir(output_dir / "logs", "*.log", keep)
    metrics_removed = _prune_dir(output_dir / "metrics_logs", "*_metrics.log", keep)

    print(f"Pruned {logs_removed} log(s) and {metrics_removed} metrics log(s)")
    return logs_removed, metrics_removed


def _prune_dir(directory: Path, pattern: str, keep: int) -> int:
    if not directory.exists():
        return 0
    files = sorted(
        directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )
    stale = files[keep:]
    for path in stale:
        path.unlink()
        print(f"Removed {directory.name}/{path.name}")
    return len(stale)
