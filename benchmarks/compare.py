"""Compare CPU time and peak memory of end-to-end scenarios between two code versions.

The base side is a commit, exported to a temporary directory (usually develop).
The PR side is the working tree this script runs from.
Each side gets its own environment, its own Cython build and its own datasets.
Runs alternate between the sides, each in a fresh process and with the dataset caches
removed, so every run includes building the dataset cache.
The report is a verdict and a Markdown table of medians, meant for a PR comment.
A change beyond the threshold of its metric is flagged as a regression or improvement.
Wall time is reported for context only, since load from other jobs on the machine
changes it.

Run it through nox with the base commit after ``--``::

    nox -s benchmark -- --base develop
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "test_output"
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
SCENARIOS = ("saturated_rh", "saturated_sm")
REPEATS = 3
# About three times the spread of one commit's runs on the CI runner, at least 1%. Twenty
# runs of the saturated scenarios spread by 1.2% in CPU time and 0.25% in peak memory
CPU_TIME_THRESHOLD_PCT = 3.5
PEAK_MEMORY_THRESHOLD_PCT = 1.0
# String hashes decide set order and thread pools add noise to CPU time
PINNED_ENV = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
BUILD_DATASETS = (
    "from tests.end_to_end.end_to_end_shared import build_e2e_datasets; "
    "build_e2e_datasets()"
)
RUN_SCENARIO = (
    "import sys; "
    "from simulation.helper.configuration.configuration import Configuration; "
    "from simulation.simulation import Simulation; "
    "Simulation(Configuration(sys.argv[1])).run_simulation()"
)
# The unit of ru_maxrss is bytes on macOS and kilobytes on Linux
MAXRSS_BYTES = 1 if sys.platform == "darwin" else 1024


@dataclass(frozen=True, slots=True)
class Side:
    """
    One of the two code versions under comparison.

    Parameters
    ----------
    name : str
        Label in the report and in the log, either base or PR.
    root : Path
        Directory the side's code is installed from and runs in.
    environment : Path
        Virtual environment the side is installed into.
    """

    name: str
    root: Path
    environment: Path

    @property
    def python(self) -> Path:
        """Interpreter of the side's environment."""
        return self.environment / "bin" / "python"


@dataclass(frozen=True, slots=True)
class Sample:
    """
    Resource usage of one scenario run.

    Parameters
    ----------
    cpu_time_s : float
        User plus system CPU time.
    peak_memory_bytes : int
        Peak resident memory.
    wall_time_s : float
        Elapsed wall-clock time.
    """

    cpu_time_s: float
    peak_memory_bytes: int
    wall_time_s: float


@dataclass(frozen=True, slots=True)
class Metric:
    """
    One column of the report.

    Parameters
    ----------
    label : str
        Column heading in the report.
    value : Callable
        Function reading the value from a sample.
    unit : str
        Unit shown after the value.
    scale : float
        Factor from the sample's unit to the shown unit.
    threshold_pct : float or None
        Change beyond which a cell gets flagged (percent). None never flags a cell.
    """

    label: str
    value: Callable[[Sample], float]
    unit: str
    scale: float
    threshold_pct: float | None


METRICS = (
    Metric("CPU time", attrgetter("cpu_time_s"), "s", 1.0, CPU_TIME_THRESHOLD_PCT),
    Metric(
        "Peak memory",
        attrgetter("peak_memory_bytes"),
        "MB",
        1e-6,
        PEAK_MEMORY_THRESHOLD_PCT,
    ),
    Metric("Wall time", attrgetter("wall_time_s"), "s", 1.0, None),
)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the comparison and write its report.

    A regression does not raise, it only gets flagged in the report.

    Parameters
    ----------
    argv : sequence of str or None
        Command line arguments. None reads them from ``sys.argv``.

    Raises
    ------
    subprocess.CalledProcessError
        If git fails, or the installation, dataset build or a run of a side.
    """
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args.report.write_text(_compare(args.base))
    logger.info("Report written to %s", args.report)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base", required=True, help="commit to compare against, e.g. develop"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=OUTPUT_DIR / "benchmark-report.md",
        help="Markdown file the report is written to (default: %(default)s)",
    )
    return parser.parse_args(argv)


def _compare(base: str) -> str:
    base_commit = subprocess.run(
        ("git", "rev-parse", "--verify", f"{base}^{{commit}}"),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()
    # Inside the checkout, so a CI clean removes what a cancelled run leaves behind
    with tempfile.TemporaryDirectory(prefix="benchmark-", dir=OUTPUT_DIR) as tmp:
        workdir = Path(tmp)
        _export(base_commit, workdir / "base")
        base_side = Side("base", workdir / "base", workdir / "base-env")
        pr_side = Side("PR", ROOT, workdir / "pr-env")
        sides = (base_side, pr_side)
        for side in sides:
            _install(side)
            # The first import compiles bytecode, so building the datasets keeps that
            # CPU time out of the measured runs
            _build_datasets(side)
        samples = _measure_all(sides)
    return _report(samples, base_side, pr_side, base_commit)


def _export(commit: str, destination: Path) -> None:
    logger.info("Exporting %s to %s", commit, destination)
    archive = subprocess.run(
        ("git", "archive", commit), cwd=ROOT, stdout=subprocess.PIPE, check=True
    )
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(destination, filter="data")


def _install(side: Side) -> None:
    logger.info("Installing %s into %s", side.name, side.environment)
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(side.environment)}
    env.pop("VIRTUAL_ENV", None)
    subprocess.run(
        ("uv", "sync", "--locked", "--no-dev", "--python", PYTHON_VERSION),
        cwd=side.root,
        env=env,
        check=True,
    )
    # Forced rebuild as in the nox test sessions, so no stale Cython build gets reused
    subprocess.run(
        (
            "uv",
            "pip",
            "install",
            "-e",
            ".",
            "--force-reinstall",
            "--no-deps",
            "--python",
            str(side.python),
        ),
        cwd=side.root,
        env=env,
        check=True,
    )


def _build_datasets(side: Side) -> None:
    logger.info("Building datasets of %s", side.name)
    subprocess.run(
        (str(side.python), "-c", BUILD_DATASETS),
        cwd=side.root,
        env=_pinned_env(),
        check=True,
    )


def _pinned_env() -> dict[str, str]:
    env = {**os.environ, **PINNED_ENV}
    env.pop("VIRTUAL_ENV", None)
    # A PYTHONPATH entry would win over the editable install and mix the sides
    env.pop("PYTHONPATH", None)
    return env


def _measure_all(sides: Sequence[Side]) -> dict[tuple[str, Side], list[Sample]]:
    samples: dict[tuple[str, Side], list[Sample]] = defaultdict(list)
    for repeat in range(REPEATS):
        # Alternate the order so a slow phase of the machine hits both sides
        order = sides if repeat % 2 == 0 else sides[::-1]
        for scenario in SCENARIOS:
            for side in order:
                sample = _measure(side, scenario)
                logger.info(
                    "%s on %s, run %d of %d: %.1f s CPU, %.0f MB peak, %.1f s wall",
                    scenario,
                    side.name,
                    repeat + 1,
                    REPEATS,
                    sample.cpu_time_s,
                    sample.peak_memory_bytes * 1e-6,
                    sample.wall_time_s,
                )
                samples[scenario, side].append(sample)
    return samples


def _measure(side: Side, scenario: str) -> Sample:
    # A run writes nothing into its dataset but the cache (a side keeping its cache
    # elsewhere would run warm after its first run)
    for cache in (side.root / "data" / "datasets").glob("e2e_*/.cache"):
        shutil.rmtree(cache)
    config_dir = side.root / "tests" / "configurations" / scenario
    command = (str(side.python), "-c", RUN_SCENARIO, str(config_dir))
    start = time.perf_counter()
    process = subprocess.Popen(command, cwd=side.root, env=_pinned_env())
    # wait4 gives this child's own usage, getrusage only the sum over all children
    _, status, usage = os.wait4(process.pid, 0)
    wall_time_s = time.perf_counter() - start
    process.returncode = os.waitstatus_to_exitcode(status)
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)
    return Sample(
        cpu_time_s=usage.ru_utime + usage.ru_stime,
        peak_memory_bytes=usage.ru_maxrss * MAXRSS_BYTES,
        wall_time_s=wall_time_s,
    )


def _report(
    samples: dict[tuple[str, Side], list[Sample]],
    base_side: Side,
    pr_side: Side,
    base_commit: str,
) -> str:
    rows = []
    flagged = []
    for scenario in SCENARIOS:
        cells = []
        for metric in METRICS:
            base = statistics.median(map(metric.value, samples[scenario, base_side]))
            pr = statistics.median(map(metric.value, samples[scenario, pr_side]))
            change, is_flagged = _change(base, pr, metric.threshold_pct)
            cells.append(
                f"{change} ({base * metric.scale:.1f} → "
                f"{pr * metric.scale:.1f} {metric.unit})"
            )
            if is_flagged:
                flagged.append(f"- {metric.label} of {scenario}: {change}")
        rows.append(f"| {scenario} | {' | '.join(cells)} |")
    verdict = ["**Flagged:**", "", *flagged] if flagged else ["**No flagged changes.**"]
    return (
        "\n".join(
            [
                "## Benchmark",
                "",
                *verdict,
                "",
                f"| Scenario | {' | '.join(metric.label for metric in METRICS)} |",
                "|---" * (len(METRICS) + 1) + "|",
                *rows,
                "",
                f"Base `{base_commit[:8]}` against the PR on Python {PYTHON_VERSION}, "
                f"median of {REPEATS} runs per side, base → PR in parentheses.",
                f"A CPU time change beyond {CPU_TIME_THRESHOLD_PCT:g}% or a peak memory "
                f"change beyond {PEAK_MEMORY_THRESHOLD_PCT:g}% is flagged. "
                "Wall time is for context only.",
            ]
        )
        + "\n"
    )


def _change(base: float, pr: float, threshold_pct: float | None) -> tuple[str, bool]:
    change_pct = (pr - base) / base * 100
    # A change that rounds to zero shows as 0.0%, never as -0.0%
    change = f"{change_pct:+.1f}%" if round(change_pct, 1) else "0.0%"
    is_flagged = threshold_pct is not None and abs(change_pct) > threshold_pct
    if is_flagged:
        change = f"**{change} {'regression' if change_pct > 0 else 'improvement'}**"
    return change, is_flagged


if __name__ == "__main__":
    main()
