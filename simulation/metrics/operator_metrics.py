"""Operator-specific metrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from simulation.helper.configuration.enums import TaskState

if TYPE_CHECKING:
    from simulation.operator.operator import Operator

from .metrics_base import IndexedMetricsBase
from .metrics_dict import MetricsDict


class OperatorMetrics(IndexedMetricsBase):
    """
    Metrics class for operator-specific metrics.

    Provides both individual operator metrics and aggregated metrics.
    Operators can be accessed by their ID using indexed access (e.g. `metrics['operator_id']`).
    """

    def list_available_uids(self) -> list[str]:
        """Get list of all available operator IDs."""
        return [operator.uid for operator in self._simulation.world.operators]

    def get_metrics_by_uid(self, operator_id: str) -> MetricsDict:
        """Get metrics for a specific operator by ID."""
        operator = self._get_operator_by_id(operator_id)
        if operator is None:
            raise KeyError(f"Operator with ID '{operator_id}' not found")
        return self._get_operator_metrics(operator)

    def to_dict(self) -> MetricsDict:
        """Return metrics for all operators plus aggregate metrics."""
        metrics = MetricsDict()
        aggregate = {
            "total_revenue": 0.0,
            "total_transaction_count": 0,
            "total_fulfilled_trips": 0,
            "trip_fulfillment_rate": [],
            "total_missed_trips": 0,
            "total_missed_revenue": 0.0,
            "total_trip_duration": 0.0,
            "total_trip_distance": 0.0,
            "total_energy_consumption": 0.0,
            "total_service_tasks_scheduled": 0,
            "finished_service_tasks": 0,
        }

        for operator in self._simulation.world.operators:
            op_metrics = self._get_operator_metrics(operator)
            metrics[operator.uid] = op_metrics

            # Add to aggregate metrics
            tx_metrics = operator.transaction_log.metrics
            aggregate["total_revenue"] += tx_metrics.total_revenue
            aggregate["total_transaction_count"] += (
                operator.transaction_log.transaction_count
            )
            aggregate["total_fulfilled_trips"] += tx_metrics.total_fulfilled_trips
            aggregate["trip_fulfillment_rate"].append(tx_metrics.trip_fulfillment_rate)
            aggregate["total_missed_trips"] += tx_metrics.total_missed_trips
            aggregate["total_missed_revenue"] += tx_metrics.total_missed_revenue
            aggregate["total_trip_duration"] += tx_metrics.total_trip_duration
            aggregate["total_trip_distance"] += tx_metrics.total_trip_distance
            aggregate["total_energy_consumption"] += tx_metrics.total_energy_consumption
            aggregate["total_service_tasks_scheduled"] += op_metrics[
                "total_service_tasks_scheduled"
            ]
            aggregate["finished_service_tasks"] += op_metrics["finished_service_tasks"]

        aggregate["trip_fulfillment_rate"] = np.mean(aggregate["trip_fulfillment_rate"])
        metrics["aggregate"] = MetricsDict(aggregate)
        return metrics

    def _get_operator_by_id(self, operator_id: str) -> Operator | None:
        """Find an operator by its ID."""
        for operator in self._simulation.world.operators:
            if operator.uid == operator_id:
                return operator
        return None

    def _get_operator_metrics(self, operator: Operator) -> MetricsDict:
        """Get metrics for a single operator."""
        transaction_metrics = operator.transaction_log.metrics
        service_tasks_by_state = operator.operations.service_tasks_by_state  # TODO: only used for debugging in IntegratedSharedMobilityOperations, generalize
        return MetricsDict(
            {
                "total_revenue": transaction_metrics.total_revenue,
                "total_transaction_count": operator.transaction_log.transaction_count,
                "total_fulfilled_trips": transaction_metrics.total_fulfilled_trips,
                "total_missed_trips": transaction_metrics.total_missed_trips,
                "total_missed_revenue": transaction_metrics.total_missed_revenue,
                "total_trip_duration": transaction_metrics.total_trip_duration,
                "average_trip_duration": transaction_metrics.average_trip_duration,
                "total_trip_distance": transaction_metrics.total_trip_distance,
                "average_trip_distance": transaction_metrics.average_trip_distance,
                "average_trip_price": transaction_metrics.average_trip_price,
                "trip_fulfillment_rate": transaction_metrics.trip_fulfillment_rate,
                "total_energy_consumption": transaction_metrics.total_energy_consumption,
                "average_energy_consumption": transaction_metrics.average_energy_consumption,
                "total_service_tasks_scheduled": sum(service_tasks_by_state.values()),
                "finished_service_tasks": service_tasks_by_state[TaskState.FINISHED],
                "initialized_service_tasks": service_tasks_by_state[
                    TaskState.INITIALIZED
                ],
                "executing_charging_service_tasks": service_tasks_by_state[
                    TaskState.EXECUTING_CHARGING
                ],
                "executing_relocation_service_tasks": service_tasks_by_state[
                    TaskState.EXECUTING_RELOCATION
                ],
            }
        )
