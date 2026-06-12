"""Health checks for datasets and projects.

Can be expanded over time as needed (Or thrown in the bin).
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import h3  # type: ignore[import-untyped]
import pandas as pd
import pyarrow.parquet as pq

from scripts._cli.paths import REPO_ROOT, project_dataset_dir
from simulation.helper.enums import VehicleType
from simulation.world.demand import demand_schema

if TYPE_CHECKING:
    from pathlib import Path

_PROJECT_FILES = ("config.toml", "operators.py", "population.py", "run.py")

_DEMAND_COLUMNS = frozenset(
    {
        demand_schema.ORIGIN,
        demand_schema.DESTINATION,
        demand_schema.TIME_BUCKET,
        demand_schema.IS_WEEKEND,
        demand_schema.ORIGIN_ARRIVAL_RATE,
        demand_schema.DESTINATION_PROBABILITY,
    }
)

_SUPPLY_COLUMNS = frozenset({"hex_id", "vehicle_type", "probability"})

_OPTIONAL_TRANSIT_FILES = ("transit_timetable.parquet", "transit_shapes.parquet")

# Tolerance for per-cell destination-probability sums.
_PROB_SUM_TOL = 1e-6


def diagnose(root: Path = REPO_ROOT) -> list[str]:
    """Scan datasets and projects for inconsistencies.

    Parameters
    ----------
    root : Path
        Repository root. Defaults to the project root.

    Returns
    -------
    list of str
        Human-readable issue strings. Empty when no issues found.
    """
    issues: list[str] = []
    issues.extend(_check_datasets(root / "data" / "datasets"))
    issues.extend(_check_projects(root / "data" / "projects"))
    return issues


def _check_datasets(datasets_dir: Path) -> list[str]:
    if not datasets_dir.exists():
        return []
    issues: list[str] = []
    for dataset_dir in sorted(p for p in datasets_dir.iterdir() if p.is_dir()):
        name = dataset_dir.name
        if not (dataset_dir / "bounding_box.geojson").exists():
            issues.append(f"dataset '{name}': missing bounding_box.geojson")
        demand_path = dataset_dir / "demand.parquet"
        if not demand_path.exists():
            issues.append(f"dataset '{name}': missing demand.parquet")
        else:
            issues.extend(_check_demand(name, demand_path))
        supply_path = dataset_dir / "supply.parquet"
        if supply_path.exists():
            issues.extend(_check_supply(name, supply_path))
        issues.extend(_check_transit(name, dataset_dir))
    return issues


def _check_demand(name: str, demand_path: Path) -> list[str]:
    try:
        columns = set(pq.read_schema(demand_path).names)
    except (OSError, ValueError) as exc:
        return [f"dataset '{name}': demand.parquet is unreadable ({exc})"]
    missing = _DEMAND_COLUMNS - columns
    if missing:
        return [
            f"dataset '{name}': demand.parquet missing column(s) "
            f"{sorted(missing)}; expected {sorted(_DEMAND_COLUMNS)}"
        ]

    try:
        df = pd.read_parquet(demand_path, columns=sorted(_DEMAND_COLUMNS))
    except (OSError, ValueError) as exc:
        return [f"dataset '{name}': demand.parquet is unreadable ({exc})"]

    if df.empty:
        return [f"dataset '{name}': demand.parquet has no rows"]

    issues: list[str] = []
    cells = pd.unique(
        pd.concat([df[demand_schema.ORIGIN], df[demand_schema.DESTINATION]])
    )
    invalid = [c for c in cells if not h3.is_valid_cell(c)]
    if invalid:
        issues.append(
            f"dataset '{name}': demand.parquet has invalid H3 cell(s) "
            f"(e.g. {invalid[:3]})"
        )

    if (df[demand_schema.ORIGIN_ARRIVAL_RATE] <= 0).any():
        issues.append(
            f"dataset '{name}': demand.parquet has non-positive "
            f"{demand_schema.ORIGIN_ARRIVAL_RATE} value(s)"
        )

    sums = df.groupby(
        [demand_schema.ORIGIN, demand_schema.TIME_BUCKET, demand_schema.IS_WEEKEND]
    )[demand_schema.DESTINATION_PROBABILITY].sum()
    if (sums - 1.0).abs().max() > _PROB_SUM_TOL:
        issues.append(
            f"dataset '{name}': demand.parquet "
            f"{demand_schema.DESTINATION_PROBABILITY} does not sum to 1 per "
            f"(origin, time_bucket, is_weekend) cell"
        )
    return issues


def _check_supply(name: str, supply_path: Path) -> list[str]:
    try:
        df = pd.read_parquet(supply_path)
    except (OSError, ValueError) as exc:
        return [f"dataset '{name}': supply.parquet is unreadable ({exc})"]

    missing = _SUPPLY_COLUMNS - set(df.columns)
    if missing:
        return [
            f"dataset '{name}': supply.parquet missing column(s) "
            f"{sorted(missing)}; expected {sorted(_SUPPLY_COLUMNS)}"
        ]
    if df.empty:
        return [f"dataset '{name}': supply.parquet has no rows"]

    issues: list[str] = []
    try:
        for vehicle_type in df["vehicle_type"].unique():
            VehicleType(vehicle_type)
    except ValueError as exc:
        issues.append(
            f"dataset '{name}': supply.parquet has invalid vehicle_type ({exc})"
        )

    hex_ids = df["hex_id"].astype(str)
    invalid = [c for c in hex_ids.unique() if not h3.is_valid_cell(c)]
    if invalid:
        issues.append(
            f"dataset '{name}': supply.parquet has invalid H3 cell(s) "
            f"(e.g. {invalid[:3]})"
        )
    else:
        resolutions = {h3.get_resolution(c) for c in hex_ids.unique()}
        if len(resolutions) > 1:
            issues.append(
                f"dataset '{name}': supply.parquet mixes H3 resolutions "
                f"{sorted(resolutions)}"
            )

    totals = df.groupby("vehicle_type")["probability"].sum()
    zero_types = totals[totals == 0.0].index.tolist()
    if zero_types:
        issues.append(
            f"dataset '{name}': supply.parquet has zero total probability for "
            f"vehicle type(s) {sorted(map(str, zero_types))}"
        )
    return issues


def _check_transit(name: str, dataset_dir: Path) -> list[str]:
    issues: list[str] = []
    for fname in _OPTIONAL_TRANSIT_FILES:
        path = dataset_dir / fname
        if not path.exists():
            continue
        try:
            pq.read_schema(path)
        except (OSError, ValueError) as exc:
            issues.append(f"dataset '{name}': {fname} is unreadable ({exc})")
    return issues


def _check_projects(projects_dir: Path) -> list[str]:
    if not projects_dir.exists():
        return []
    issues: list[str] = []
    for project_dir in sorted(p for p in projects_dir.iterdir() if p.is_dir()):
        name = project_dir.name
        missing = [f for f in _PROJECT_FILES if not (project_dir / f).exists()]
        for fname in missing:
            issues.append(f"project '{name}': missing {fname}")
        issues.extend(_check_project_dataset_link(project_dir))
        if not missing:
            issues.extend(_check_project_loads(project_dir))
    return issues


def _check_project_dataset_link(project_dir: Path) -> list[str]:
    try:
        dataset_dir = project_dataset_dir(project_dir)
    except FileNotFoundError:
        # Missing config.toml is already reported by _check_projects.
        return []
    except tomllib.TOMLDecodeError as exc:
        return [f"project '{project_dir.name}': config.toml is malformed ({exc})"]
    except ValueError:
        return [f"project '{project_dir.name}': config.toml has no PATH.DATASET_DIR"]

    if not dataset_dir.exists():
        return [
            f"project '{project_dir.name}': DATASET_DIR points at missing path {dataset_dir}"
        ]
    return []


def _check_project_loads(project_dir: Path) -> list[str]:
    """Load the project as a Configuration to surface config/operator/fleet errors."""
    # Imported lazily so a broken simulation import never breaks the whole scan.
    from simulation.helper.configuration.configuration import Configuration

    try:
        config = Configuration(str(project_dir))
        if not config.operators or config.population is None:
            return [f"project '{project_dir.name}': operators.py defines no operators"]
    except Exception as exc:  # diagnostic must report, not crash
        return [f"project '{project_dir.name}': failed to load config ({exc})"]
    return []
