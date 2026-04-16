"""Operator-specific metrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from simulation.helper.types import SimId
    from simulation.operator.operator import Operator

from ..metrics_base import IndexedMetricsBase
from ..metrics_dict import MetricsDict


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
        aggregate = {
            "total_revenue": 0.0,
            "total_transaction_count": 0,
            "total_fulfilled_trips": 0,
            "trip_fulfillment_rate": [],
            "total_missed_allocations": 0,
            "total_missed_revenue": 0.0,
            "total_trip_duration": 0.0,
            "total_trip_distance": 0.0,
            "total_energy_consumption": 0.0,
        }

        for operator in self._simulation.world.operators:
            op_metrics = self._get_operator_metrics(operator)
            metrics[operator.uid] = op_metrics

            # Add to aggregate metrics
            operator_log_stats = operator.operator_log.metrics
            aggregate["total_revenue"] += operator_log_stats.total_revenue
            aggregate["total_transaction_count"] += (
                operator.operator_log.transaction_count
            )
            aggregate["total_fulfilled_trips"] += (
                operator_log_stats.total_fulfilled_trips
            )
            aggregate["trip_fulfillment_rate"].append(
                operator_log_stats.trip_fulfillment_rate
            )
            aggregate["total_missed_allocations"] += (
                operator_log_stats.total_missed_trips
            )
            aggregate["total_missed_revenue"] += operator_log_stats.total_missed_revenue
            aggregate["total_trip_duration"] += operator_log_stats.total_trip_duration
            aggregate["total_trip_distance"] += operator_log_stats.total_trip_distance
            aggregate["total_energy_consumption"] += (
                operator_log_stats.total_energy_consumption
            )

        aggregate["trip_fulfillment_rate"] = np.mean(aggregate["trip_fulfillment_rate"])
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
        operator_log_stats = operator.operator_log.metrics
        return MetricsDict(
            {
                "total_revenue": operator_log_stats.total_revenue,
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
        )
