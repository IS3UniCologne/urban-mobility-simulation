"""CLI path and location constants and helpers."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
TEMPLATES_DIR = SCRIPTS_DIR / "_templates"
PRESETS_FILE = SCRIPTS_DIR / "_presets.toml"


def project_dataset_dir(project_dir: Path) -> Path:
    """Get a project's dataset directory from its config."""
    config_path = project_dir / "config.toml"
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    raw = data.get("PATH", {}).get("DATASET_DIR")
    if raw is None:
        raise ValueError(f"{config_path} has no PATH.DATASET_DIR")
    dataset_dir = Path(raw).expanduser()
    if not dataset_dir.is_absolute():
        dataset_dir = (project_dir / dataset_dir).resolve()
    return dataset_dir
