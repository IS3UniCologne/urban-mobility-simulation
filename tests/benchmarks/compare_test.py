"""Tests for the flagging of changes in the benchmark report."""

import pytest

from benchmarks.compare import _change


@pytest.mark.parametrize(
    ("base", "pr", "threshold_pct", "expected"),
    [
        (100.0, 104.0, 5.0, "+4.0%"),
        (100.0, 106.0, 5.0, "+6.0% **regression**"),
        (100.0, 94.0, 5.0, "-6.0% **improvement**"),
        (100.0, 150.0, None, "+50.0%"),
    ],
)
def test_change_flags_only_beyond_threshold(
    base: float, pr: float, threshold_pct: float | None, expected: str
) -> None:
    assert _change(base, pr, threshold_pct) == expected
