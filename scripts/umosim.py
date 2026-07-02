r"""CLI tool for scaffolding simulation datasets and projects."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tomllib
from pathlib import Path

# Ensure repo root is always on the path, no matter where this script is run from.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts._cli.cleanup import clean_demos, clean_logs
from scripts._cli.doctor import diagnose
from scripts._cli.orchestrators import demo, generate_demand, init_dataset, new_project
from scripts._cli.paths import project_dataset_dir
from scripts._cli.prompts import (
    ensure_required_arg,
    is_interactive,
    prompt_choice,
    prompt_float,
    prompt_int,
    prompt_multi_choice,
    prompt_text,
    prompt_yes_no,
)
from scripts._cli.synthetic_demand import DemandParams
from scripts._cli.templates import list_starters, load_presets

logger = logging.getLogger(__name__)

# Demand modifiers for synthetic demand generation, used to build both argparse and prompts.
# Each tuple is: (name, type, metavar, help_text).
_DEMAND_MODIFIERS: tuple[tuple[str, type, str, str], ...] = (
    ("base_arrival_rate", float, "RATE", "arrival-rate ceiling at the busiest hex"),
    ("min_arrival_rate", float, "RATE", "arrival-rate floor"),
    ("n_hotspots", int, "N", "number of demand hotspots"),
    (
        "hotspot_decay",
        float,
        "FRAC",
        "how quickly demand drops off away from hotspots (0=sharp, 1=gradual)",
    ),
    (
        "self_trip_share",
        float,
        "FRAC",
        "share of trips that start and end in the same hex(0-1)",
    ),
    (
        "gravity_alpha",
        float,
        "ALPHA",
        "how strongly distance suppresses demand (0=no suppression)",
    ),
    (
        "demand_noise_std",
        float,
        "STD",
        "additive noise to demand (as fraction of arrival rate)",
    ),
)
_DEMAND_PATTERN_FIELDS = ("weekday_pattern", "weekend_pattern")
_DEMAND_FIELDS = tuple(dest for dest, *_ in _DEMAND_MODIFIERS) + _DEMAND_PATTERN_FIELDS


def _resolve_bbox(args: argparse.Namespace) -> tuple[float, float, float, float] | None:
    """Resolve a bbox from CLI args."""
    preset = getattr(args, "preset", None)
    bbox_str = getattr(args, "bbox", None)
    if preset is not None:
        presets = load_presets()
        if preset not in presets:
            raise SystemExit(
                f"Unknown preset '{preset}'. Available: {sorted(presets) or '<none>'}"
            )
        return presets[preset]
    if bbox_str is not None:
        try:
            parts = [float(x) for x in bbox_str.split(",")]
        except ValueError as exc:
            raise SystemExit(
                "--bbox must be four comma-separated floats: "
                "lat_min,lon_min,lat_max,lon_max"
            ) from exc
        if len(parts) != 4:
            raise SystemExit("--bbox needs exactly four comma-separated floats")
        return (parts[0], parts[1], parts[2], parts[3])
    return None


_VERBOSE_BBOX_LABELS = (
    "lat_min (decimal deg, e.g. 52.41)",
    "lon_min (decimal deg, e.g. 13.37)",
    "lat_max (decimal deg, e.g. 52.62)",
    "lon_max (decimal deg, e.g. 13.65)",
)


def _prompt_bbox_selection(
    args: argparse.Namespace, labels: tuple[str, ...] = _VERBOSE_BBOX_LABELS
) -> None:
    presets = load_presets()
    selection = prompt_choice("Bounding box", [*sorted(presets), "manual"])
    if selection == "manual":
        args.bbox = ",".join(prompt_text(label) for label in labels)
    else:
        args.preset = selection


def _add_bbox_args(parser: argparse.ArgumentParser, presets: list[str]) -> None:
    group = parser.add_mutually_exclusive_group()
    preset_help = (
        f"Named bbox preset (choices: {', '.join(presets)})"
        if presets
        else "Named bbox preset"
    )
    group.add_argument("--preset", metavar="NAME", help=preset_help)
    group.add_argument(
        "--bbox",
        metavar="LAT_MIN,LON_MIN,LAT_MAX,LON_MAX",
        help="Bounding box as lat_min,lon_min,lat_max,lon_max",
    )


def _resolve_demand_params(args: argparse.Namespace) -> DemandParams | None:
    """Build DemandParams from CLI flags, or from an interactive prompt."""
    overrides = {
        field: getattr(args, field)
        for field in _DEMAND_FIELDS
        if getattr(args, field) is not None
    }
    if overrides:
        return DemandParams.from_mapping(overrides)

    if is_interactive() and prompt_yes_no("\nCustomize synthetic demand?"):
        defaults = DemandParams()
        prompted = {
            dest: (prompt_int if kind is int else prompt_float)(
                f"  {dest.replace('_', ' ')} ({help_text})", getattr(defaults, dest)
            )
            for dest, kind, _, help_text in _DEMAND_MODIFIERS
        }
        return DemandParams.from_mapping(prompted)
    return None


def _print_dataset_next_steps(name: str) -> None:
    print(
        f"\nDataset '{name}' is ready (synthetic demand). To use your own data, "
        f"overwrite any of: demand.parquet, supply.parquet, "
        f"transit_timetable.parquet, transit_shapes.parquet."
    )
    print(f"Next: umosim new-project <project-name> --dataset {name}")


def _print_project_next_steps(name: str) -> None:
    print(
        f"\nProject '{name}' scaffolded. Edit operators.py / population.py / "
        f"config.toml to customize the experiment."
    )
    print(f"Next: umosim run {name}")


def _handle_new_dataset(args: argparse.Namespace) -> None:
    args.name = ensure_required_arg(
        args.name,
        missing_message="new-dataset: 'name' is required",
        prompt=lambda: prompt_text("Dataset name"),
    )
    bbox = _resolve_bbox(args)
    if bbox is None:
        if not is_interactive():
            raise SystemExit("new-dataset requires --preset or --bbox")
        _prompt_bbox_selection(args)
        bbox = _resolve_bbox(args)
    if bbox is None:
        raise SystemExit("new-dataset: could not resolve bounding box")

    params = _resolve_demand_params(args)
    init_dataset(args.name, bbox, force=args.force)
    generate_demand(
        args.name,
        spatial_resolution=args.spatial_resolution,
        temporal_resolution=args.temporal_resolution,
        seed=args.seed,
        params=params,
    )
    _print_dataset_next_steps(args.name)


def _handle_new_project(args: argparse.Namespace) -> None:
    args.name = ensure_required_arg(
        args.name,
        missing_message="new-project: 'name' is required",
        prompt=lambda: prompt_text("Project name"),
    )
    args.dataset = ensure_required_arg(
        args.dataset,
        missing_message="new-project: --dataset is required",
        prompt=lambda: prompt_text("Dataset name"),
    )
    if is_interactive():
        starters = list_starters()
        args.operators = prompt_multi_choice(
            "Operators to include", starters, defaults=args.operators
        )
    new_project(
        args.name,
        args.dataset,
        operators=args.operators,
        num_charging_stations=args.num_charging_stations,
        force=args.force,
    )
    _print_project_next_steps(args.name)


def _handle_demo(args: argparse.Namespace) -> None:
    projects = demo(force=args.force)
    for p in projects:
        print(f"Next: umosim run {p.name}")


def _handle_clean_demos(args: argparse.Namespace) -> None:
    del args
    clean_demos()


def _handle_clean_logs(args: argparse.Namespace) -> None:
    clean_logs(keep=args.keep)


def _handle_doctor(args: argparse.Namespace) -> None:
    del args
    issues = diagnose()
    if not issues:
        print("All checks passed.")
        return
    for issue in issues:
        print(issue)
    raise SystemExit(1)


def _resolve_project_dataset(project_dir: Path) -> Path | None:
    """Best-effort resolve of a project's DATASET_DIR for logging."""
    try:
        return project_dataset_dir(project_dir)
    except (FileNotFoundError, tomllib.TOMLDecodeError, ValueError):
        return None


def _handle_run(args: argparse.Namespace) -> None:
    project_dir = _REPO_ROOT / "data" / "projects" / args.name
    run_script = project_dir / "run.py"
    if not run_script.exists():
        raise SystemExit(f"No run.py found at {run_script}")
    dataset_dir = _resolve_project_dataset(project_dir)
    if dataset_dir is not None:
        logger.info("Running '%s' on dataset %s", args.name, dataset_dir)
    if args.log_level is not None:
        from simulation.helper.configuration.configuration import LOG_LEVEL_ENV_VAR

        os.environ[LOG_LEVEL_ENV_VAR] = args.log_level
        logger.info("Overriding log level for this run: %s", args.log_level)
    if args.viz:
        from visualization import VIZ_ENABLED_ENV_VAR

        os.environ[VIZ_ENABLED_ENV_VAR] = "1"
        logger.info("Visualization enabled for this run")
    try:
        os.execvp("uv", ["uv", "run", str(run_script)])
    except FileNotFoundError:
        raise SystemExit("'uv' not found on PATH. Please install uv to run projects")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands wired up."""
    parser = argparse.ArgumentParser(
        prog="umosim",
        description="Scaffold simulation datasets and projects.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preset_names = sorted(load_presets().keys())
    starter_choices = list_starters() or ["rh", "sm"]

    # demo
    p_demo = subparsers.add_parser(
        "demo",
        help="Generate a synthetic demo (berlin_synthetic dataset + one project per mode).",
    )
    p_demo.add_argument(
        "--force", action="store_true", help="Overwrite existing demo dataset/projects"
    )
    p_demo.set_defaults(func=_handle_demo)

    # new-dataset
    p_dataset = subparsers.add_parser(
        "new-dataset",
        help="Create a dataset: bounding_box.geojson + synthetic demand.parquet.",
    )
    p_dataset.add_argument("name", nargs="?", default=None, help="Dataset name")
    _add_bbox_args(p_dataset, preset_names)
    p_dataset.add_argument(
        "--spatial-resolution",
        type=int,
        default=7,
        metavar="RES",
        help="H3 resolution (default: 7)",
    )
    p_dataset.add_argument(
        "--temporal-resolution",
        type=int,
        default=4,
        metavar="HOURS",
        help="Hours per time bucket (default: 4)",
    )
    p_dataset.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Synthetic-demand random seed (default: 42)",
    )
    p_dataset.add_argument(
        "--force", action="store_true", help="Overwrite existing dataset"
    )
    _add_demand_tuning_args(p_dataset)
    p_dataset.set_defaults(func=_handle_new_dataset)

    # new-project
    p_project = subparsers.add_parser(
        "new-project", help="Scaffold project files against an existing dataset."
    )
    p_project.add_argument("name", nargs="?", default=None, help="Project name")
    p_project.add_argument(
        "--dataset",
        required=False,
        default=None,
        metavar="DATASET_NAME",
        help="Dataset name (must already exist; create it with new-dataset)",
    )
    p_project.add_argument(
        "--operators",
        nargs="+",
        default=starter_choices,
        choices=starter_choices,
        metavar="TYPE",
        help=(
            "Operator types to include (choices: "
            f"{', '.join(starter_choices)}). Repeat for multiple. "
            f"Default: {' '.join(starter_choices)}"
        ),
    )
    p_project.add_argument(
        "--num-charging-stations",
        type=int,
        default=6,
        metavar="N",
        help="Number of charging station hexes (default: 6)",
    )
    p_project.add_argument(
        "--force", action="store_true", help="Overwrite existing project"
    )
    p_project.set_defaults(func=_handle_new_project)

    # clean-demos
    p_clean_demos = subparsers.add_parser(
        "clean-demos", help="Remove demo + test datasets and projects (idempotent)."
    )
    p_clean_demos.set_defaults(func=_handle_clean_demos)

    # clean-logs
    p_clean_logs = subparsers.add_parser(
        "clean-logs",
        help="Prune data/output/{logs,metrics_logs}, keeping the newest --keep entries.",
    )
    p_clean_logs.add_argument(
        "--keep",
        type=int,
        default=10,
        metavar="N",
        help="Number of newest log files to retain in each directory (default: 10)",
    )
    p_clean_logs.set_defaults(func=_handle_clean_logs)

    # doctor
    p_doctor = subparsers.add_parser(
        "doctor",
        help="Report orphan or malformed datasets and projects (exit 1 if any).",
    )
    p_doctor.set_defaults(func=_handle_doctor)

    # run
    p_run = subparsers.add_parser(
        "run", help="Run a project's run.py via uv (e.g. umosim run ridehailing_demo)."
    )
    p_run.add_argument("name", help="Project name (directory under data/projects/)")
    log_group = p_run.add_mutually_exclusive_group()
    log_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        dest="log_level",
        help="Override console + file log level for this run (ignores config.toml).",
    )
    log_group.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const="DEBUG",
        dest="log_level",
        help="Shortcut for --log-level DEBUG.",
    )
    log_group.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const="CRITICAL",
        dest="log_level",
        help="Shortcut for --log-level CRITICAL (near-silent console).",
    )
    p_run.add_argument(
        "--viz",
        action="store_true",
        dest="viz",
        help="Enable the live visualization dashboard for this run "
        "(requires the 'viz' extra: uv sync --extra viz).",
    )
    p_run.set_defaults(func=_handle_run)

    return parser


def _add_demand_tuning_args(parser: argparse.ArgumentParser) -> None:
    """Add the optional synthetic-demand modifiers as a dedicated, advanced group."""
    defaults = DemandParams()
    group = parser.add_argument_group("synthetic demand tuning (advanced, optional)")
    for dest, kind, metavar, help_text in _DEMAND_MODIFIERS:
        group.add_argument(
            f"--{dest.replace('_', '-')}",
            type=kind,
            default=None,
            metavar=metavar,
            help=f"{help_text} (default: {getattr(defaults, dest)})",
        )
    group.add_argument(
        "--weekday-pattern",
        type=float,
        nargs="+",
        default=None,
        metavar="M",
        help="Weekday diurnal multipliers per 4h bucket (resampled to bucket count)",
    )
    group.add_argument(
        "--weekend-pattern",
        type=float,
        nargs="+",
        default=None,
        metavar="M",
        help="Weekend diurnal multipliers per 4h bucket (resampled to bucket count)",
    )


def main() -> None:
    """CLI entrypoint."""
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (FileExistsError, FileNotFoundError, ValueError, OSError) as exc:
        raise SystemExit(f"Error: {exc}") from None


if __name__ == "__main__":
    main()
