"""Operator-specific metrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from simulation.helper.types import SimId
    from simulation.operator.operator import Operator

from simulation.operator.cost_accounting import CostType

from ..metrics_base import IndexedMetricsBase
from ..metrics_dict import MetricsDict

_COST_KEYS = tuple(f"cost_{cost_type.value}" for cost_type in CostType)

_SUMMED_AGGREGATE_KEYS = (
    "total_revenue",
    "total_transaction_count",
    "total_fulfilled_trips",
    "total_missed_revenue",
    "total_trip_duration",
    "total_trip_distance",
    "total_energy_consumption",
    "total_cost",
)


class OperatorMetrics(IndexedMetricsBase):
    """
    Metrics class for operator-specific metrics.

    Provides both individual operator metrics and aggregated metrics.
    Operators can be accessed by their ID using indexed access (e.g. `operator_metrics['operator_id']`).

    Parameters
    ----------
    simulation : Simulation
        The main simulation instance.
    """

    def list_available_uids(self) -> list[SimId]:
        """Get list of all available operator IDs."""
        return [operator.uid for operator in self._simulation.world.operators]

    def get_metrics_by_uid(self, uid: SimId) -> MetricsDict:
        """Get metrics for a specific operator by ID."""
        operator = self._get_operator_by_id(uid)
        if operator is None:
            raise KeyError(f"Operator with ID '{uid}' not found")
        return self._get_operator_metrics(operator)

    def to_dict(self) -> MetricsDict:
        """Return metrics for all operators plus aggregate metrics."""
        metrics = MetricsDict()
        summed_keys = (*_SUMMED_AGGREGATE_KEYS, *_COST_KEYS)
        totals: dict[str, float] = dict.fromkeys(summed_keys, 0)
        trip_fulfillment_rates: list[float] = []
        total_missed_allocations = 0

        for operator in self._simulation.world.operators:
            op_metrics = self._operator_metric_values(operator)
            metrics[operator.uid] = MetricsDict(op_metrics)

            for key in summed_keys:
                totals[key] += op_metrics[key]
            total_missed_allocations += int(op_metrics["total_missed_trips"])
            trip_fulfillment_rates.append(op_metrics["trip_fulfillment_rate"])

        aggregate = {
            **totals,
            "trip_fulfillment_rate": (
                float(np.mean(trip_fulfillment_rates))
                if trip_fulfillment_rates
                else 0.0
            ),
            "total_missed_allocations": total_missed_allocations,
            "profit": totals["total_revenue"] - totals["total_cost"],
        }
        metrics["aggregate"] = MetricsDict(aggregate)
        return metrics

    def _get_operator_by_id(self, operator_id: SimId) -> Operator | None:
        """Find an operator by its ID."""
        for operator in self._simulation.world.operators:
            if operator.uid == operator_id:
                return operator
        return None

    def _get_operator_metrics(self, operator: Operator) -> MetricsDict:
        """Get metrics for a single operator."""
        return MetricsDict(self._operator_metric_values(operator))

    def _operator_metric_values(self, operator: Operator) -> dict[str, float]:
        """Get metrics for a single operator, before MetricsDict wrapping.

        Returns a plain typed dict so callers can aggregate numerically;
        `MetricsDict` erases value types to `object`.
        """
        operator_log_stats = operator.operator_log.metrics
        ledger = operator.cost_ledger
        costs_by_type = ledger.totals_by_type()
        total_cost = sum(costs_by_type.values())
        revenue = ledger.revenue()
        cost_metrics = {
            f"cost_{cost_type.value}": amount
            for cost_type, amount in costs_by_type.items()
        }
        return {
            **cost_metrics,
            "total_cost": total_cost,
            "profit": revenue - total_cost,
            "total_revenue": revenue,
            "total_transaction_count": operator.operator_log.transaction_count,
            "total_fulfilled_trips": operator_log_stats.total_fulfilled_trips,
            "total_missed_trips": operator_log_stats.total_missed_trips,
            "total_missed_revenue": operator_log_stats.total_missed_revenue,
            "total_trip_duration": operator_log_stats.total_trip_duration,
            "average_trip_duration": operator_log_stats.average_trip_duration,
            "total_trip_distance": operator_log_stats.total_trip_distance,
            "average_trip_distance": operator_log_stats.average_trip_distance,
            "average_trip_price": operator_log_stats.average_trip_price,
            "trip_fulfillment_rate": operator_log_stats.trip_fulfillment_rate,
            "total_energy_consumption": operator_log_stats.total_energy_consumption,
            "average_energy_consumption": operator_log_stats.average_energy_consumption,
        }
