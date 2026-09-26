"""Datasets the test projects point at, built from the presets in ``scripts/``."""

from __future__ import annotations

import shutil
from pathlib import Path

from filelock import FileLock

from scripts._cli.orchestrators import generate_demand, init_dataset
from scripts._cli.paths import project_dataset_dir
from scripts._cli.templates import load_preset_demand_params, load_presets

_ROOT = Path(__file__).resolve().parent.parent
_DATASETS = _ROOT / "data" / "datasets"
_CONFIG_ROOTS = (_ROOT / "tests" / "configurations",)
DEMAND_SEED = 42
_STAMP = ".build_inputs"


def _dataset_name(config_dir: Path) -> str:
    return project_dataset_dir(config_dir).name


def _required_datasets() -> list[str]:
    return sorted(
        {
            _dataset_name(d)
            for config_root in _CONFIG_ROOTS
            for d in config_root.iterdir()
            if d.is_dir() and (d / "config.toml").exists()
        }
    )


def ensure_datasets() -> None:
    """Build every dataset a test project references that is missing or out of date.

    Each dataset has a stamp with the preset, demand parameters and seed it was built from.
    The dataset is up to date while the stamp matches the current values.
    A change to the generator code itself still needs a rebuild by hand: delete the dataset directory.
    A file lock keeps xdist workers from building the same dataset at once.
    """
    _DATASETS.mkdir(parents=True, exist_ok=True)
    with FileLock(_DATASETS / ".build.lock"):
        presets = load_presets()
        for name in _required_datasets():
            stamp = _DATASETS / name / _STAMP
            if not stamp.exists() or stamp.read_text() != _inputs(name, presets):
                _build_dataset(name, presets)


def rebuild_datasets() -> None:
    """Regenerate every dataset the test projects reference."""
    presets = load_presets()
    for name in _required_datasets():
        _build_dataset(name, presets)


def _build_dataset(
    name: str, presets: dict[str, tuple[float, float, float, float]]
) -> None:
    inputs = _inputs(name, presets)
    dataset_dir = _DATASETS / name
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
    init_dataset(name, presets[name], root=_ROOT)
    generate_demand(
        name, root=_ROOT, seed=DEMAND_SEED, params=load_preset_demand_params(name)
    )
    (dataset_dir / _STAMP).write_text(inputs)


def _inputs(name: str, presets: dict[str, tuple[float, float, float, float]]) -> str:
    """Return the preset, demand parameters and seed a dataset is built from."""
    if name not in presets:
        raise ValueError(
            f"Dataset '{name}' referenced by a test project has no preset in "
            f"scripts/_presets.toml."
        )
    return repr((presets[name], load_preset_demand_params(name), DEMAND_SEED))
