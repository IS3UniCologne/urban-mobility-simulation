"""Orchestrator functions for the CLI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from scripts._cli.bbox import load_bbox_hexes
from scripts._cli.paths import REPO_ROOT
from scripts._cli.synthetic_demand import DemandParams, create_synthetic_demand_file
from scripts._cli.templates import (
    build_config_toml,
    build_operators_py,
    build_population_py,
    build_run_py,
    list_starters,
    load_presets,
)
from simulation.world.demand import demand_schema

if TYPE_CHECKING:
    from pathlib import Path

DEMO_DATASET = "berlin_synthetic"
DEMO_PRESET = "berlin"
DEMO_SEED = 42

DEMO_PROJECT_NAMES = {
    "admission": "ridehailing_admission_demo",
    "rh": "ridehailing_demo",
    "sm": "sharedmobility_demo",
}


def _box_to_geojson(bbox: tuple[float, float, float, float]) -> dict:
    lat_min, lon_min, lat_max, lon_max = bbox
    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "environment"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [lon_min, lat_min],
                            [lon_max, lat_min],
                            [lon_max, lat_max],
                            [lon_min, lat_max],
                            [lon_min, lat_min],
                        ]
                    ],
                },
            }
        ],
    }


def init_dataset(
    name: str,
    bbox: tuple[float, float, float, float],
    root: Path = REPO_ROOT,
    force: bool = False,
) -> Path:
    """Create a dataset directory with bounding_box.geojson.

    Parameters
    ----------
    name : str
        Dataset name (becomes directory name under data/datasets/).
    bbox : tuple of float
        Bounding box as (lat_min, lon_min, lat_max, lon_max).
    root : Path
        Repository root. Defaults to the project root.
    force : bool
        Overwrite if the dataset directory already exists.

    Returns
    -------
    Path
        Path to the created dataset directory.

    Raises
    ------
    FileExistsError
        If the dataset directory already exists and force is False.
    """
    dataset_dir = root / "data" / "datasets" / name
    if dataset_dir.exists() and not force:
        raise FileExistsError(
            f"Dataset '{name}' already exists at {dataset_dir}. Pass force=True to overwrite."
        )
    dataset_dir.mkdir(parents=True, exist_ok=True)

    bbox_geojson = _box_to_geojson(bbox)

    bbox_path = dataset_dir / "bounding_box.geojson"
    with open(bbox_path, "w") as f:
        json.dump(bbox_geojson, f, indent=2)

    print(f"Created {bbox_path.relative_to(root)}")

    return dataset_dir


def generate_demand(
    dataset_name: str,
    root: Path = REPO_ROOT,
    spatial_resolution: int = 7,
    temporal_resolution: int = 4,
    seed: int = 42,
    params: DemandParams | None = None,
) -> None:
    """Generate synthetic demand for a dataset.

    Parameters
    ----------
    dataset_name : str
        Name of an existing dataset (must have bounding_box.geojson).
    root : Path
        Repository root.
    spatial_resolution : int
        H3 resolution for hex grid (default 7).
    temporal_resolution : int
        Hours per time bucket (default 4).
    seed : int
        Random seed for reproducibility.
    params : DemandParams or None
        Demand modifiers. Defaults to ``DemandParams()``.

    Raises
    ------
    FileNotFoundError
        If bounding_box.geojson does not exist in the dataset directory.
    ValueError
        If no hexes exist at the given resolution inside the bounding box.
    """
    dataset_dir = root / "data" / "datasets" / dataset_name
    bbox_path = dataset_dir / "bounding_box.geojson"
    if not bbox_path.exists():
        raise FileNotFoundError(
            f"bounding_box.geojson not found at {bbox_path}. "
            f"Run 'umosim new-dataset {dataset_name}' first."
        )

    hex_ids = load_bbox_hexes(bbox_path, spatial_resolution)
    if not hex_ids:
        raise ValueError(
            f"No hexes at resolution {spatial_resolution} inside bounding box."
        )
    print(f"  {len(hex_ids)} hexes at resolution {spatial_resolution}")

    rng = np.random.default_rng(seed)
    create_synthetic_demand_file(
        hex_ids, dataset_dir, temporal_resolution, rng, root=root, params=params
    )


def _top_demand_hexes(demand_path: Path, n: int) -> list[str]:
    df = pd.read_parquet(
        demand_path,
        columns=[
            demand_schema.ORIGIN,
            demand_schema.TIME_BUCKET,
            demand_schema.IS_WEEKEND,
            demand_schema.ORIGIN_ARRIVAL_RATE,
        ],
    )
    # Arrival rate repeats per destination row, drop duplicates firts
    cells = df.drop_duplicates(
        [demand_schema.ORIGIN, demand_schema.TIME_BUCKET, demand_schema.IS_WEEKEND]
    )
    totals = cells.groupby(demand_schema.ORIGIN)[
        demand_schema.ORIGIN_ARRIVAL_RATE
    ].sum()
    return totals.nlargest(n).index.tolist()


def new_project(
    name: str,
    dataset_name: str,
    operators: list[str] | None = None,
    root: Path = REPO_ROOT,
    num_charging_stations: int = 6,
    force: bool = False,
) -> Path:
    """Create a project directory with config.toml, operators.py, population.py, run.py.

    Needs an existing dataset to reference.

    Parameters
    ----------
    name : str
        Project name (becomes directory name under data/projects/).
    dataset_name : str
        Name of the dataset this project uses.
    operators : list of str or None
        Operators to include. Defaults to all available.
    root : Path
        Repository root. Defaults to the project root.
    num_charging_stations : int
        Number of charging station hexes to include in configs.
    force : bool
        Overwrite if the project directory already exists.

    Returns
    -------
    Path
        Path to the created project directory.

    Raises
    ------
    FileExistsError
        If the project directory already exists and force is False.
    FileNotFoundError
        If the dataset's bounding_box.geojson or demand.parquet does not exist.
    ValueError
        If an unrecognized operator type is provided.
    """
    if operators is None:
        operators = ["rh", "sm"]

    valid_starters = set(list_starters())
    unknown = [t for t in operators if t not in valid_starters]
    if unknown:
        raise ValueError(
            f"Unknown operator type(s): {unknown}. Known: {sorted(valid_starters)}."
        )

    dataset_dir = root / "data" / "datasets" / dataset_name
    bbox_path = dataset_dir / "bounding_box.geojson"
    if not bbox_path.exists():
        raise FileNotFoundError(
            f"bounding_box.geojson not found at {bbox_path}. "
            f"Run 'umosim new-dataset {dataset_name}' first."
        )
    if not (dataset_dir / "demand.parquet").exists():
        raise FileNotFoundError(
            f"demand.parquet not found in dataset '{dataset_name}'. "
            f"Run 'umosim new-dataset {dataset_name}' first."
        )

    project_dir = root / "data" / "projects" / name
    if project_dir.exists() and not force:
        raise FileExistsError(
            f"Project '{name}' already exists at {project_dir}. Pass force=True to overwrite."
        )
    project_dir.mkdir(parents=True, exist_ok=True)

    station_hexes = _top_demand_hexes(
        dataset_dir / "demand.parquet", num_charging_stations
    )

    config_toml = build_config_toml(dataset_name)
    operators_py = build_operators_py(operators, station_hexes)
    population_py = build_population_py()
    run_py = build_run_py(operators)

    (project_dir / "config.toml").write_text(config_toml)
    (project_dir / "operators.py").write_text(operators_py)
    (project_dir / "population.py").write_text(population_py)
    (project_dir / "run.py").write_text(run_py)

    for fname in ("config.toml", "operators.py", "population.py", "run.py"):
        print(f"  Wrote {(project_dir / fname).relative_to(root)}")

    return project_dir


def demo(root: Path = REPO_ROOT, force: bool = False) -> list[Path]:
    """Generate a demo project for each starter.

    Returns
    -------
    list of Path
        Paths to the created demo projects, sorted by starter name.
    """
    presets = load_presets()
    if DEMO_PRESET not in presets:
        raise ValueError(f"Demo preset '{DEMO_PRESET}' not found in presets file.")
    bbox = presets[DEMO_PRESET]
    starters = list_starters()
    if not starters:
        raise ValueError("No starter templates found in scripts/_templates/")

    dataset_dir = root / "data" / "datasets" / DEMO_DATASET
    if not dataset_dir.exists() or force:
        init_dataset(DEMO_DATASET, bbox, root=root, force=force)
    if not (dataset_dir / "demand.parquet").exists() or force:
        generate_demand(DEMO_DATASET, root=root, seed=DEMO_SEED)

    project_paths: list[Path] = []
    for starter in starters:
        project_name = DEMO_PROJECT_NAMES.get(starter, f"{starter}_demo")
        path = new_project(
            project_name, DEMO_DATASET, operators=[starter], root=root, force=force
        )
        project_paths.append(path)
    return project_paths
