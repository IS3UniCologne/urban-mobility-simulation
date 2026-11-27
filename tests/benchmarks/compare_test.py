"""Tests for the scenario selection and the flagging of changes in the benchmark report."""

from pathlib import Path

import pytest

from benchmarks.compare import (
    SCENARIOS,
    Sample,
    Side,
    _change,
    _report,
    _shared_scenarios,
)


@pytest.mark.parametrize(
    ("base", "pr", "threshold_pct", "expected"),
    [
        (100.0, 104.0, 5.0, ("+4.0%", False)),
        (100.0, 106.0, 5.0, ("**+6.0% regression**", True)),
        (100.0, 94.0, 5.0, ("**-6.0% improvement**", True)),
        (100.0, 150.0, None, ("+50.0%", False)),
        (100.0, 99.99, 5.0, ("0.0%", False)),
    ],
)
def test_change_flags_only_beyond_threshold(
    base: float, pr: float, threshold_pct: float | None, expected: tuple[str, bool]
) -> None:
    assert _change(base, pr, threshold_pct) == expected


def side(root: Path, scenarios: tuple[str, ...]) -> Side:
    """Build a side that has a configuration for each of the scenarios."""
    for scenario in scenarios:
        (root / "tests" / "configurations" / scenario).mkdir(parents=True)
    return Side(root.name, root, root / "env")


def test_shared_scenarios_leaves_out_a_scenario_one_side_lacks(tmp_path: Path) -> None:
    base = side(tmp_path / "base", SCENARIOS[:-1])
    pr = side(tmp_path / "PR", SCENARIOS)

    assert _shared_scenarios((base, pr)) == list(SCENARIOS[:-1])


def test_report_names_the_scenarios_it_does_not_compare(tmp_path: Path) -> None:
    base = side(tmp_path / "base", SCENARIOS[:1])
    pr = side(tmp_path / "PR", SCENARIOS[:1])
    sample = Sample(cpu_time_s=1.0, peak_memory_bytes=1, wall_time_s=1.0)
    samples = {(SCENARIOS[0], base): [sample], (SCENARIOS[0], pr): [sample]}

    report = _report(samples, SCENARIOS[:1], base, pr, "0" * 40)

    assert f"| {SCENARIOS[0]} |" in report
    assert f"| {SCENARIOS[1]} |" not in report
    assert f"no such scenario: {', '.join(SCENARIOS[1:])}." in report
