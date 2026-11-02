"""Unit tests for Bookkeeper."""

from __future__ import annotations

import pytest

from rl.bookkeeper import Bookkeeper
from rl.problem import Period
from simulation.operator.accounting import CostType
from tests.rl.fakes import make_fulfilled, make_missed, make_operator

pytestmark = pytest.mark.unit


def test_entries_before_construction_are_excluded() -> None:
    """Only revenue and entries after the bookkeeper opened are settled."""
    operator = make_operator([])
    operator.operator_log.transactions.append(make_fulfilled("a", price=100.0))
    operator.ledger.revenue_total = 100.0

    bookkeeper = Bookkeeper(operator)
    operator.operator_log.transactions.append(make_fulfilled("a", price=7.0))
    operator.ledger.revenue_total += 7.0
    period = bookkeeper.settle(Period(0.0, 15.0))

    assert (period.start_min, period.end_min) == (0.0, 15.0)
    assert period.revenue == pytest.approx(7.0)
    assert len(period.transactions) == 1


def test_consecutive_periods_do_not_overlap() -> None:
    """Each log entry and each unit of cost lands in one period, profit nets every cost type."""
    operator = make_operator([])
    bookkeeper = Bookkeeper(operator)

    operator.operator_log.transactions.extend(
        [make_fulfilled("a", price=30.0), make_missed("b")]
    )
    operator.ledger.revenue_total = 30.0
    operator.ledger.costs[CostType.VEHICLE_RELOCATION_DISTANCE] = 10.0
    operator.ledger.costs[CostType.VEHICLE_HOLDING] = 4.0
    first = bookkeeper.settle(Period(0.0, 15.0))

    operator.operator_log.transactions.append(make_fulfilled("c", price=5.0))
    operator.ledger.revenue_total += 5.0
    second = bookkeeper.settle(Period(15.0, 30.0))

    assert (first.start_min, first.end_min) == (0.0, 15.0)
    assert (second.start_min, second.end_min) == (15.0, 30.0)
    assert first.revenue == pytest.approx(30.0)
    assert first.fulfilled == 1
    assert second.revenue == pytest.approx(5.0)
    assert first.costs_by_type[CostType.VEHICLE_RELOCATION_DISTANCE] == 10.0
    assert first.cost == pytest.approx(14.0)
    assert first.profit == pytest.approx(16.0)
    assert second.cost == 0.0
    assert [entry.origin for entry in first.transactions] == ["a", "b"]
    assert [entry.origin for entry in second.transactions] == ["c"]
    assert bookkeeper.settlement is second
