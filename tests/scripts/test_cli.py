"""Tests for the ``umosim`` CLI orchestrators."""

import json
import os
import re
import shutil
from pathlib import Path

import h3
import pandas as pd
import pytest

from scripts._cli.bbox import load_bbox_hexes
from scripts._cli.cleanup import TEST_DATASETS, clean_demos, clean_logs
from scripts._cli.doctor import diagnose
from scripts._cli.orchestrators import (
    DEMO_DATASET,
    DEMO_PROJECT_NAMES,
    demo,
    generate_demand,
    init_dataset,
    new_project,
)
from scripts._cli.paths import TEMPLATES_DIR
from scripts._cli.synthetic_demand import DemandParams
from simulation.world.demand import demand_schema

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Small bounding box (central Munich area)
_BBOX = (48.10, 11.40, 48.25, 11.55)
_DATASET = "testcity"


@pytest.fixture()
def source_root(tmp_path: Path) -> Path:
    """tmp_path masquerading as a umosim source checkout (has pyproject.toml)."""
    (tmp_path / "pyproject.toml").touch()
    return tmp_path


@pytest.fixture()
def dataset_dir(tmp_path: Path) -> Path:
    """Dataset directory with bounding_box.geojson."""
    return init_dataset(_DATASET, _BBOX, root=tmp_path)


@pytest.fixture()
def dataset_with_demand(dataset_dir: Path, tmp_path: Path) -> Path:
    """Dataset directory with bounding_box.geojson and demand.parquet."""
    generate_demand(
        _DATASET, root=tmp_path, spatial_resolution=7, temporal_resolution=4, seed=42
    )
    return dataset_dir


# ---------------------------------------------------------------------------
# init_dataset (orchestrator API)
# ---------------------------------------------------------------------------


def test_init_dataset_creates_geojson(tmp_path: Path) -> None:
    dataset_dir = init_dataset(_DATASET, _BBOX, root=tmp_path)

    bbox_path = dataset_dir / "bounding_box.geojson"
    assert bbox_path.exists()

    with open(bbox_path) as f:
        gj = json.load(f)

    assert gj["type"] == "FeatureCollection"
    feature = gj["features"][0]
    assert feature["geometry"]["type"] == "Polygon"

    coords = feature["geometry"]["coordinates"][0]
    # Ring must be closed (first == last)
    assert coords[0] == coords[-1]

    # Coords in GeoJSON order: [lon, lat]
    lat_min, lon_min, lat_max, lon_max = _BBOX
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    assert min(lons) == pytest.approx(lon_min)
    assert max(lons) == pytest.approx(lon_max)
    assert min(lats) == pytest.approx(lat_min)
    assert max(lats) == pytest.approx(lat_max)


def test_init_dataset_fails_if_exists(tmp_path: Path) -> None:
    init_dataset(_DATASET, _BBOX, root=tmp_path)
    with pytest.raises(FileExistsError, match=_DATASET):
        init_dataset(_DATASET, _BBOX, root=tmp_path)


def test_init_dataset_force_overwrites(tmp_path: Path) -> None:
    init_dataset(_DATASET, _BBOX, root=tmp_path)
    # Should not raise
    init_dataset(_DATASET, _BBOX, root=tmp_path, force=True)


# ---------------------------------------------------------------------------
# generate_demand
# ---------------------------------------------------------------------------


def test_generate_demand_demand_schema(dataset_dir: Path, tmp_path: Path) -> None:
    generate_demand(_DATASET, root=tmp_path)

    df = pd.read_parquet(dataset_dir / "demand.parquet")
    assert set(df.columns) == {
        demand_schema.ORIGIN,
        demand_schema.DESTINATION,
        demand_schema.TIME_BUCKET,
        demand_schema.IS_WEEKEND,
        demand_schema.ORIGIN_ARRIVAL_RATE,
        demand_schema.DESTINATION_PROBABILITY,
    }
    assert (df[demand_schema.ORIGIN_ARRIVAL_RATE] > 0).all()


def test_generate_demand_destination_probabilities_sum_to_one(
    dataset_dir: Path, tmp_path: Path
) -> None:
    generate_demand(_DATASET, root=tmp_path)

    df = pd.read_parquet(dataset_dir / "demand.parquet")
    sums = df.groupby(
        [demand_schema.ORIGIN, demand_schema.TIME_BUCKET, demand_schema.IS_WEEKEND]
    )[demand_schema.DESTINATION_PROBABILITY].sum()
    assert (sums - 1.0).abs().max() < 1e-6


def test_generate_demand_fails_without_bbox(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"bounding_box\.geojson"):
        generate_demand("nonexistent", root=tmp_path)


def test_generate_demand_demand_is_deterministic(
    dataset_dir: Path, tmp_path: Path
) -> None:
    generate_demand(_DATASET, root=tmp_path, seed=42)
    first = (dataset_dir / "demand.parquet").read_bytes()
    (dataset_dir / "demand.parquet").unlink()
    generate_demand(_DATASET, root=tmp_path, seed=42)
    second = (dataset_dir / "demand.parquet").read_bytes()
    assert first == second


def test_generate_demand_has_self_loops(dataset_dir: Path, tmp_path: Path) -> None:
    generate_demand(_DATASET, root=tmp_path)

    df = pd.read_parquet(dataset_dir / "demand.parquet")
    self_loops = df[df[demand_schema.ORIGIN] == df[demand_schema.DESTINATION]]
    assert not self_loops.empty


def test_generate_demand_concentrates_demand(tmp_path: Path) -> None:
    # Larger bbox (Berlin) so the heavy-tailed concentration is visible across
    # many hexes rather than the handful in the small default test box.
    name = "bigcity"
    dataset_dir = init_dataset(name, (52.40, 13.20, 52.60, 13.50), root=tmp_path)
    generate_demand(name, root=tmp_path)

    df = pd.read_parquet(dataset_dir / "demand.parquet")
    bbox_path = dataset_dir / "bounding_box.geojson"
    total_hexes = len(load_bbox_hexes(bbox_path, spatial_resolution=7))

    # Every bbox hex remains a spatial unit (none dropped).
    assert df[demand_schema.ORIGIN].nunique() == total_hexes

    per_hex = (
        df.drop_duplicates(
            [demand_schema.ORIGIN, demand_schema.TIME_BUCKET, demand_schema.IS_WEEKEND]
        )
        .groupby(demand_schema.ORIGIN)[demand_schema.ORIGIN_ARRIVAL_RATE]
        .sum()
        .sort_values(ascending=False)
    )
    # Heavy-tailed: the busiest 20% of hexes carry the majority of all demand.
    top_share = per_hex.head(max(1, len(per_hex) // 5)).sum() / per_hex.sum()
    assert top_share > 0.6


def test_generate_demand_base_arrival_rate_scales_volume(
    dataset_dir: Path, tmp_path: Path
) -> None:
    generate_demand(
        _DATASET, root=tmp_path, params=DemandParams(base_arrival_rate=20.0)
    )
    low = pd.read_parquet(dataset_dir / "demand.parquet")[
        demand_schema.ORIGIN_ARRIVAL_RATE
    ].sum()

    generate_demand(
        _DATASET, root=tmp_path, params=DemandParams(base_arrival_rate=80.0)
    )
    high = pd.read_parquet(dataset_dir / "demand.parquet")[
        demand_schema.ORIGIN_ARRIVAL_RATE
    ].sum()

    assert high > low


def test_demand_params_from_mapping_defaults_and_overrides() -> None:
    # Missing keys fall back to dataclass defaults; provided keys override.
    params = DemandParams.from_mapping({"base_arrival_rate": 7.0, "n_hotspots": 1})
    defaults = DemandParams()
    assert params.base_arrival_rate == 7.0
    assert params.n_hotspots == 1
    assert params.gravity_alpha == defaults.gravity_alpha


def test_demand_params_from_mapping_coerces_patterns_to_tuple() -> None:
    params = DemandParams.from_mapping({"weekday_pattern": [1.0, 2.0, 3.0]})
    assert params.weekday_pattern == (1.0, 2.0, 3.0)


def test_demand_params_from_mapping_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match=r"Unknown demand parameter"):
        DemandParams.from_mapping({"bogus_knob": 1.0})


def test_load_preset_demand_params_defaults_when_no_table() -> None:
    # The `berlin` preset carries no [berlin.demand] table -> defaults.
    from scripts._cli.templates import load_preset_demand_params

    assert load_preset_demand_params("berlin") == DemandParams()


def test_load_preset_demand_params_reads_overrides() -> None:
    # The `e2e_saturated` preset pins the pre-retune peak arrival rate.
    from scripts._cli.templates import load_preset_demand_params

    assert load_preset_demand_params("e2e_saturated").base_arrival_rate == 130.0


# ---------------------------------------------------------------------------
# new_project
# ---------------------------------------------------------------------------


def test_new_project_config_toml_dataset_path(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    project_dir = new_project("proj", _DATASET, operators=["rh"], root=tmp_path)

    config = (project_dir / "config.toml").read_text()
    assert f'DATASET_DIR      = "../../datasets/{_DATASET}"' in config


def test_new_project_run_py_imports_simulation(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    project_dir = new_project("proj", _DATASET, operators=["rh"], root=tmp_path)
    content = (project_dir / "run.py").read_text()
    assert "from simulation.simulation import Simulation" in content
    assert "Configuration(" in content


def test_new_project_population_py_defines_population(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    project_dir = new_project("proj", _DATASET, operators=["rh"], root=tmp_path)

    content = (project_dir / "population.py").read_text()
    assert "POPULATION = PopulationConfig(" in content


def test_new_project_operators_py_rh_is_valid(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    from simulation.helper.configuration.configuration import RideHailingOperatorConfig

    project_dir = new_project("proj_rh", _DATASET, operators=["rh"], root=tmp_path)
    operators = _exec_operators((project_dir / "operators.py").read_text())

    assert len(operators) == 1
    assert isinstance(operators[0], RideHailingOperatorConfig)


def test_new_project_operators_py_sm_is_valid(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    from simulation.helper.configuration.configuration import (
        SharedVehicleOperatorConfig,
    )

    project_dir = new_project("proj_sm", _DATASET, operators=["sm"], root=tmp_path)
    operators = _exec_operators((project_dir / "operators.py").read_text())

    assert len(operators) == 1
    assert isinstance(operators[0], SharedVehicleOperatorConfig)


def test_new_project_hex_ids_are_valid_h3(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    project_dir = new_project("proj", _DATASET, operators=["rh"], root=tmp_path)
    content = (project_dir / "operators.py").read_text()

    hex_ids = re.findall(r'"([0-9a-f]{15})"', content)
    assert len(hex_ids) > 0
    for hex_id in hex_ids:
        assert h3.is_valid_cell(hex_id), f"Invalid H3 cell: {hex_id}"


def _exec_operators(content: str) -> list[object]:
    """Exec a rendered ``operators.py`` and return its ``OPERATORS`` list."""
    namespace: dict[str, object] = {}
    exec(content, namespace)
    operators = namespace["OPERATORS"]
    assert isinstance(operators, list)
    return operators


def test_new_project_multiple_operators(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    from simulation.helper.configuration.configuration import (
        RideHailingOperatorConfig,
        SharedVehicleOperatorConfig,
    )

    project_dir = new_project(
        "proj_multi", _DATASET, operators=["rh", "rh", "sm"], root=tmp_path
    )
    operators = _exec_operators((project_dir / "operators.py").read_text())

    assert len(operators) == 3
    assert isinstance(operators[0], RideHailingOperatorConfig)
    assert isinstance(operators[1], RideHailingOperatorConfig)
    assert isinstance(operators[2], SharedVehicleOperatorConfig)


def test_new_project_duplicate_operators_are_independent(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    """Repeating a starter yields separate operator objects with separate nested
    configs, so editing one does not affect the other."""
    project_dir = new_project(
        "proj_dup", _DATASET, operators=["rh", "rh"], root=tmp_path
    )
    op1, op2 = _exec_operators((project_dir / "operators.py").read_text())

    assert op1 is not op2
    assert op1.CHARGING_INFRASTRUCTURE is not op2.CHARGING_INFRASTRUCTURE
    assert op1.FLEET_CONFIG is not op2.FLEET_CONFIG


def test_starter_run_py_is_used_for_a_single_starter_project(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    """A project with one operator from a starter with its own run.py gets it.

    A mixed project and a repeated starter get the shared one, since the
    starter's runner acts for exactly one operator.
    """
    own = new_project(
        "proj_admission", _DATASET, operators=["admission"], root=tmp_path
    )
    mixed = new_project(
        "proj_mixed", _DATASET, operators=["rh", "admission"], root=tmp_path
    )
    repeated = new_project(
        "proj_repeated", _DATASET, operators=["admission", "admission"], root=tmp_path
    )

    starter_run_py = (TEMPLATES_DIR / "admission" / "run.py").read_text()
    shared_run_py = (TEMPLATES_DIR / "run.py").read_text()
    assert (own / "run.py").read_text() == starter_run_py
    assert (mixed / "run.py").read_text() == shared_run_py
    assert (repeated / "run.py").read_text() == shared_run_py


def test_new_project_fails_if_exists(dataset_with_demand: Path, tmp_path: Path) -> None:
    new_project("proj", _DATASET, operators=["rh"], root=tmp_path)
    with pytest.raises(FileExistsError, match="proj"):
        new_project("proj", _DATASET, operators=["rh"], root=tmp_path)


def test_new_project_fails_without_bbox(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"bounding_box\.geojson"):
        new_project("proj", "nonexistent", operators=["rh"], root=tmp_path)
    # No stranded project directory should be left behind.
    assert not (tmp_path / "data" / "projects" / "proj").exists()


def test_new_project_fails_without_demand(dataset_dir: Path, tmp_path: Path) -> None:
    # bounding_box.geojson present (dataset_dir fixture) but no demand.parquet.
    with pytest.raises(FileNotFoundError, match=r"demand\.parquet"):
        new_project("proj", _DATASET, operators=["rh"], root=tmp_path)
    assert not (tmp_path / "data" / "projects" / "proj").exists()


def test_new_project_force_overwrites(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    new_project("proj", _DATASET, operators=["rh"], root=tmp_path)
    # Should not raise
    new_project("proj", _DATASET, operators=["rh"], root=tmp_path, force=True)


@pytest.mark.parametrize("starter", ["admission", "rh", "sm"])
def test_new_project_config_has_no_population_section(
    starter: str, dataset_with_demand: Path, tmp_path: Path
) -> None:
    # Population is configured in population.py; config.toml must not carry a
    # dead [POPULATION] section for either starter.
    project_dir = new_project(
        f"proj_{starter}", _DATASET, operators=[starter], root=tmp_path
    )
    config = (project_dir / "config.toml").read_text()
    assert "[POPULATION]" not in config


@pytest.mark.parametrize("starter", ["admission", "rh", "sm"])
def test_starter_template_is_standalone_valid(starter: str) -> None:
    """Each starter template must be importable on its own and expose OPERATORS.

    Templates are concatenated by the scaffolder but must also be runnable as-is
    so they can be edited and tested directly.
    """
    from scripts._cli.templates import _read_template
    from simulation.helper.configuration.configuration import OperatorConfig

    namespace: dict[str, object] = {}
    exec(_read_template(starter, "operators.py"), namespace)

    operators = namespace["OPERATORS"]
    assert isinstance(operators, list)
    assert operators
    assert all(isinstance(op, OperatorConfig) for op in operators)


# ---------------------------------------------------------------------------
# demo (deterministic bootstrap)
# ---------------------------------------------------------------------------


def test_demo_creates_one_project_per_starter(tmp_path: Path) -> None:
    project_paths = demo(root=tmp_path)

    expected_names = {
        "ridehailing_admission_demo",
        "ridehailing_demo",
        "sharedmobility_demo",
    }
    assert {p.name for p in project_paths} == expected_names

    dataset_dir = tmp_path / "data" / "datasets" / DEMO_DATASET
    assert (dataset_dir / "demand.parquet").exists()
    for path in project_paths:
        assert (path / "config.toml").exists()
        assert (path / "operators.py").exists()


def test_demo_projects_have_one_operator(tmp_path: Path) -> None:
    """Each generated demo ships a single, runnable operator."""
    from simulation.helper.configuration.configuration import Configuration

    project_paths = demo(root=tmp_path)

    for path in project_paths:
        operators = Configuration(str(path)).operators
        assert len(operators) == 1, f"{path.name} should have one operator"


def test_demo_is_deterministic(tmp_path: Path) -> None:
    """Two demo runs from a clean tmp_path must produce byte-identical output."""
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    run1.mkdir()
    run2.mkdir()

    paths1 = demo(root=run1)
    paths2 = demo(root=run2)

    assert [p.name for p in paths1] == [p.name for p in paths2]
    for p1, p2 in zip(paths1, paths2, strict=True):
        for filename in ("config.toml", "operators.py", "population.py", "run.py"):
            assert (p1 / filename).read_bytes() == (p2 / filename).read_bytes(), (
                f"non-deterministic content in {filename}"
            )


# ---------------------------------------------------------------------------
# clean_demos / clean_logs / doctor
# ---------------------------------------------------------------------------


def _seed_log_files(directory: Path, names: list[str]) -> list[Path]:
    """Create empty log files with strictly increasing mtimes; return in creation order."""
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    base_mtime = 1_700_000_000.0
    for i, name in enumerate(names):
        path = directory / name
        path.touch()
        os.utime(path, (base_mtime + i, base_mtime + i))
        paths.append(path)
    return paths


def test_clean_demos_removes_demo_artifacts(source_root: Path) -> None:
    demo(root=source_root)
    # Seed the test datasets too (demo() doesn't create them).
    test_datasets = [source_root / "data" / "datasets" / name for name in TEST_DATASETS]
    for test_dataset in test_datasets:
        test_dataset.mkdir(parents=True)
        (test_dataset / "marker").touch()

    removed = clean_demos(root=source_root)

    assert not (source_root / "data" / "datasets" / DEMO_DATASET).exists()
    for test_dataset in test_datasets:
        assert not test_dataset.exists()
    for project_name in DEMO_PROJECT_NAMES.values():
        assert not (source_root / "data" / "projects" / project_name).exists()
    assert len(removed) >= 3


def test_clean_demos_idempotent_when_nothing_exists(source_root: Path) -> None:
    assert clean_demos(root=source_root) == []


def test_clean_demos_refuses_non_source_root(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="source checkout"):
        clean_demos(root=tmp_path)


def test_clean_logs_keeps_newest_n(source_root: Path) -> None:
    logs_dir = source_root / "data" / "output" / "logs"
    metrics_dir = source_root / "data" / "output" / "metrics_logs"
    log_paths = _seed_log_files(logs_dir, [f"{i:05d}.log" for i in range(15)])
    metrics_paths = _seed_log_files(
        metrics_dir, [f"{i:05d}_metrics.log" for i in range(8)]
    )

    logs_removed, metrics_removed = clean_logs(root=source_root, keep=5)

    assert logs_removed == 10
    assert metrics_removed == 3

    survivors = sorted(p.name for p in logs_dir.glob("*.log"))
    assert survivors == sorted(p.name for p in log_paths[-5:])
    metric_survivors = sorted(p.name for p in metrics_dir.glob("*_metrics.log"))
    assert metric_survivors == sorted(p.name for p in metrics_paths[-5:])


def test_clean_logs_idempotent_when_dirs_missing(source_root: Path) -> None:
    assert clean_logs(root=source_root, keep=10) == (0, 0)


def test_clean_logs_keep_zero_removes_all(source_root: Path) -> None:
    logs_dir = source_root / "data" / "output" / "logs"
    _seed_log_files(logs_dir, [f"{i}.log" for i in range(3)])

    logs_removed, _ = clean_logs(root=source_root, keep=0)

    assert logs_removed == 3
    assert list(logs_dir.glob("*.log")) == []


def test_clean_logs_rejects_negative_keep(source_root: Path) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        clean_logs(root=source_root, keep=-1)


def test_clean_logs_refuses_non_source_root(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="source checkout"):
        clean_logs(root=tmp_path, keep=5)


def test_doctor_clean_after_demo(tmp_path: Path) -> None:
    demo(root=tmp_path)
    assert diagnose(root=tmp_path) == []


def test_doctor_empty_root_is_clean(tmp_path: Path) -> None:
    assert diagnose(root=tmp_path) == []


def test_doctor_flags_orphan_project(tmp_path: Path) -> None:
    demo(root=tmp_path)
    shutil.rmtree(tmp_path / "data" / "datasets" / DEMO_DATASET)

    issues = diagnose(root=tmp_path)

    assert issues
    assert any("DATASET_DIR" in issue and DEMO_DATASET in issue for issue in issues), (
        issues
    )


def test_doctor_flags_dataset_missing_bbox(tmp_path: Path) -> None:
    foo = tmp_path / "data" / "datasets" / "foo"
    foo.mkdir(parents=True)

    issues = diagnose(root=tmp_path)

    assert any(
        "bounding_box.geojson" in issue and "foo" in issue for issue in issues
    ), issues


def test_doctor_flags_project_missing_file(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    project_dir = new_project("proj", _DATASET, operators=["rh"], root=tmp_path)
    (project_dir / "operators.py").unlink()

    issues = diagnose(root=tmp_path)

    assert any("operators.py" in issue and "proj" in issue for issue in issues), issues


def test_doctor_flags_malformed_demand_schema(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    # Overwrite the synthetic demand with a parquet missing required columns.
    demand_path = dataset_with_demand / "demand.parquet"
    pd.DataFrame({"wrong": [1, 2, 3]}).to_parquet(demand_path, index=False)

    issues = diagnose(root=tmp_path)

    assert any("demand.parquet" in issue and _DATASET in issue for issue in issues), (
        issues
    )


def test_doctor_flags_empty_demand(dataset_with_demand: Path, tmp_path: Path) -> None:
    # Right columns, zero rows.
    demand_path = dataset_with_demand / "demand.parquet"
    df = pd.read_parquet(demand_path)
    df.iloc[0:0].to_parquet(demand_path, index=False)

    issues = diagnose(root=tmp_path)

    assert any("no rows" in issue and _DATASET in issue for issue in issues), issues


def test_doctor_flags_invalid_h3_in_demand(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    demand_path = dataset_with_demand / "demand.parquet"
    df = pd.read_parquet(demand_path)
    df.loc[df.index[0], demand_schema.ORIGIN] = "not_a_hex"
    df.to_parquet(demand_path, index=False)

    issues = diagnose(root=tmp_path)

    assert any("invalid H3" in issue and _DATASET in issue for issue in issues), issues


def test_doctor_flags_nonpositive_arrival_rate(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    demand_path = dataset_with_demand / "demand.parquet"
    df = pd.read_parquet(demand_path)
    df.loc[df.index[0], demand_schema.ORIGIN_ARRIVAL_RATE] = 0.0
    df.to_parquet(demand_path, index=False)

    issues = diagnose(root=tmp_path)

    assert any(
        demand_schema.ORIGIN_ARRIVAL_RATE in issue and _DATASET in issue
        for issue in issues
    ), issues


def test_doctor_flags_demand_probabilities_not_summing_to_one(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    demand_path = dataset_with_demand / "demand.parquet"
    df = pd.read_parquet(demand_path)
    # Halve one cell's probability so the per-cell sum drifts from 1.
    idx = df.index[0]
    current = float(df.loc[idx, demand_schema.DESTINATION_PROBABILITY])
    df.loc[idx, demand_schema.DESTINATION_PROBABILITY] = current * 0.5
    df.to_parquet(demand_path, index=False)

    issues = diagnose(root=tmp_path)

    assert any(
        demand_schema.DESTINATION_PROBABILITY in issue and _DATASET in issue
        for issue in issues
    ), issues


def test_doctor_passes_with_valid_supply(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    hexes = pd.read_parquet(dataset_with_demand / "demand.parquet")[
        demand_schema.ORIGIN
    ].unique()[:3]
    pd.DataFrame(
        {
            "hex_id": list(hexes),
            "vehicle_type": ["Car"] * len(hexes),
            "probability": [1.0 / len(hexes)] * len(hexes),
        }
    ).to_parquet(dataset_with_demand / "supply.parquet", index=False)

    issues = diagnose(root=tmp_path)

    assert not any("supply.parquet" in issue for issue in issues), issues


def test_doctor_flags_malformed_supply_schema(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    pd.DataFrame({"wrong": [1, 2]}).to_parquet(
        dataset_with_demand / "supply.parquet", index=False
    )

    issues = diagnose(root=tmp_path)

    assert any("supply.parquet" in issue and _DATASET in issue for issue in issues), (
        issues
    )


def test_doctor_flags_supply_invalid_vehicle_type(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    hexes = pd.read_parquet(dataset_with_demand / "demand.parquet")[
        demand_schema.ORIGIN
    ].unique()[:2]
    pd.DataFrame(
        {
            "hex_id": list(hexes),
            "vehicle_type": ["Spaceship"] * len(hexes),
            "probability": [0.5] * len(hexes),
        }
    ).to_parquet(dataset_with_demand / "supply.parquet", index=False)

    issues = diagnose(root=tmp_path)

    assert any("vehicle_type" in issue and _DATASET in issue for issue in issues), (
        issues
    )


def test_doctor_flags_unreadable_transit(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    (dataset_with_demand / "transit_timetable.parquet").write_text("not parquet")

    issues = diagnose(root=tmp_path)

    assert any(
        "transit_timetable.parquet" in issue and _DATASET in issue for issue in issues
    ), issues


def test_doctor_flags_unloadable_project_config(
    dataset_with_demand: Path, tmp_path: Path
) -> None:
    project_dir = new_project("proj", _DATASET, operators=["rh"], root=tmp_path)
    # Syntactically broken operators.py: Configuration construction raises.
    (project_dir / "operators.py").write_text("this is fake python :) ===")

    issues = diagnose(root=tmp_path)

    assert any(
        "failed to load config" in issue and "proj" in issue for issue in issues
    ), issues
