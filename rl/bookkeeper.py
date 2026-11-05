"""Splits the revenue and cost of one operator into periods between decision points.

The ledger shows only running totals.
Each settlement subtracts the totals of the previous settlement and takes the operator log entries added since then.
``SettlementPeriod`` holds the result of one settlement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rl.problem import Period
from simulation.operator.operator_log.operator_log_entry import (
    FulfilledOperatorLogEntry,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from simulation.operator.accounting import CostType
    from simulation.operator.operator import Operator
    from simulation.operator.operator_log.operator_log_entry import OperatorLogEntry


@dataclass(frozen=True, slots=True)
class SettlementPeriod(Period):
    """
    Revenue and cost of one operator between two decision points.

    Attributes
    ----------
    start_min : float
        Simulation time the period opened (min).
    end_min : float
        Simulation time the period closed (min).
    revenue : float
        Gross fare income of trips fulfilled in the period.
    costs_by_type : mapping of CostType to float
        Cost per type, zero for unused types.
    transactions : tuple of OperatorLogEntry
        Operator log entries appended in the period.
    """

    revenue: float
    costs_by_type: Mapping[CostType, float]
    transactions: tuple[OperatorLogEntry, ...]

    @property
    def cost(self) -> float:
        """Total cost over all types."""
        return sum(self.costs_by_type.values(), 0.0)

    @property
    def profit(self) -> float:
        """Revenue minus cost."""
        return self.revenue - self.cost

    @property
    def fulfilled(self) -> int:
        """Number of trips fulfilled in the period."""
        return sum(
            isinstance(entry, FulfilledOperatorLogEntry) for entry in self.transactions
        )


class Bookkeeper:
    """
    Splits the revenue and cost of one operator into periods, one per ``settle`` call.

    Revenue, costs and log entries booked before construction belong to no period.
    The caller keeps the period clock and passes the bounds to ``settle``.
    ``settlement`` is the result of the last call.

    Parameters
    ----------
    operator : Operator
        Operator being settled.
    """

    __slots__ = (
        "_cost_baseline",
        "_operator",
        "_revenue_baseline",
        "_settlement",
        "_transaction_index",
    )

    def __init__(self, operator: Operator) -> None:
        self._operator = operator
        self._cost_baseline = operator.ledger.costs_by_type()
        self._revenue_baseline = operator.ledger.revenue()
        self._transaction_index = len(operator.operator_log.transactions)
        self._settlement: SettlementPeriod | None = None

    @property
    def operator(self) -> Operator:
        """Operator being settled."""
        return self._operator

    @property
    def settlement(self) -> SettlementPeriod:
        """Revenue, cost per type and log entries of the period settled last, or raise before the first ``settle``."""
        if self._settlement is None:
            msg = "No period is settled yet. The first settlement closes the warm-up period at the first decision point."
            raise RuntimeError(msg)
        return self._settlement

    def settle(self, period: Period) -> SettlementPeriod:
        """Close the period since the previous settlement and open the next one.

        Parameters
        ----------
        period : Period
            Bounds of the closing period, from the previous settlement or the episode start.

        Returns
        -------
        SettlementPeriod
            Revenue, cost per type and log entries of the closed period, also kept as ``settlement``.
        """
        ledger = self._operator.ledger
        running_costs = ledger.costs_by_type()
        revenue_total = ledger.revenue()
        costs = {
            cost_type: total - self._cost_baseline[cost_type]
            for cost_type, total in running_costs.items()
        }
        transactions = tuple(
            self._operator.operator_log.transactions[self._transaction_index :]
        )
        settlement = SettlementPeriod(
            start_min=period.start_min,
            end_min=period.end_min,
            revenue=revenue_total - self._revenue_baseline,
            costs_by_type=costs,
            transactions=transactions,
        )
        self._cost_baseline = running_costs
        self._revenue_baseline = revenue_total
        self._transaction_index += len(transactions)
        self._settlement = settlement
        return settlement
