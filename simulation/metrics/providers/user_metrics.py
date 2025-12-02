"""User-specific metrics module."""

from __future__ import annotations

from ..metrics_base import MetricsBase
from ..metrics_dict import MetricsDict


class UserMetrics(MetricsBase):
    """
    Metrics class for user-level metrics.

    Parameters
    ----------
    simulation : Simulation
        The main simulation instance.
    """

    def to_dict(self) -> MetricsDict:
        """
        Return all user-level metrics.

        Returns
        -------
        MetricsDict
            Dictionary containing aggregate and per-operator user metrics.
        """
        user_log = self._simulation.world.user_log
        user_log_stats = user_log.metrics

        aggregate = MetricsDict(
            {
                "total_trip_requests": user_log_stats.total_trip_requests,
                "total_fulfilled_trips": user_log_stats.total_fulfilled_trips,
                "total_missed_trips": user_log_stats.total_missed_trips,
                "fulfillment_rate": user_log_stats.fulfillment_rate,
                "fulfillment_rate_recent": user_log_stats.fulfillment_rate_recent,
                "total_revenue": user_log_stats.total_revenue,
                "average_price_paid": user_log_stats.average_price_paid,
                "total_search_time": user_log_stats.total_search_time,
                "average_search_time": user_log_stats.average_search_time,
                "average_wait_time": user_log_stats.average_wait_time,
                "total_trip_duration": user_log_stats.total_trip_duration,
                "average_trip_duration": user_log_stats.average_trip_duration,
                "total_energy_consumed": user_log_stats.total_energy_consumed,
                "average_energy_consumed": user_log_stats.average_energy_consumed,
            }
        )

        # Get per-operator stats from user perspective
        operator_stats_raw = user_log_stats.get_all_operator_stats()
        operator_stats_by_uid: MetricsDict = MetricsDict(
            {str(uid): MetricsDict(stats) for uid, stats in operator_stats_raw.items()}
        )

        return MetricsDict(
            {"aggregate": aggregate, "by_operator": operator_stats_by_uid}
        )
