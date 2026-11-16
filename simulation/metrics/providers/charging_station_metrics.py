"""Charging station metrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..metrics_base import IndexedMetricsBase
from ..metrics_dict import MetricsDict

if TYPE_CHECKING:
    from simulation.helper.types import SimId
    from simulation.infrastructure.charging_stations.charging_station import (
        ChargingStation,
    )


class ChargingStationMetrics(IndexedMetricsBase):
    """
    Metrics class for charging station-specific metrics.

    Provides both individual charging station metrics and aggregated metrics.
    Charging stations can be accessed by their location using indexed access (e.g. `metrics['station_location']`).

    Parameters
    ----------
    simulation : Simulation
        The main simulation instance.
    """

    def list_available_uids(self) -> list[SimId]:
        """Get list of all available charging station locations."""
        infrastructures = self._simulation.world.charging_infrastructures
        if infrastructures is None:
            return []
        return [
            station.uid
            for infrastructure in infrastructures
            for station in infrastructure.charging_stations
        ]

    def get_metrics_by_uid(self, uid: SimId) -> MetricsDict:
        """Get metrics for a specific charging station by location."""
        station = self._get_station_by_location(uid)
        if station is None:
            raise KeyError(f"Charging station at location '{uid}' not found")
        return self._get_station_metrics(station)

    def to_dict(self) -> MetricsDict:
        """Return metrics for all charging stations plus aggregate metrics."""
        infrastructures = self._simulation.world.charging_infrastructures
        if infrastructures is None:
            return MetricsDict()

        metrics = MetricsDict()
        total_stations = 0
        total_capacity = 0
        total_queue_capacity = 0
        total_current_users = 0
        total_current_queue_size = 0

        stations = [cs for infra in infrastructures for cs in infra.charging_stations]
        for station in stations:
            station_metrics = self._get_station_metrics(station)
            metrics[station.location] = station_metrics

            # Add to aggregate metrics
            total_stations += 1
            total_capacity += station.capacity
            total_queue_capacity += station.queue_size
            total_current_users += len(station.plugs.users)
            total_current_queue_size += len(station.plugs.queue)

        # Calculate averages
        average_utilization = 0.0
        average_queue_utilization = 0.0

        if total_stations > 0:
            total_possible_capacity = total_capacity
            total_possible_queue = total_queue_capacity

            if total_possible_capacity > 0:
                average_utilization = total_current_users / total_possible_capacity

            if total_possible_queue > 0:
                average_queue_utilization = (
                    total_current_queue_size / total_possible_queue
                )

        aggregate = {
            "total_stations": total_stations,
            "total_capacity": total_capacity,
            "total_queue_capacity": total_queue_capacity,
            "total_current_users": total_current_users,
            "total_current_queue_size": total_current_queue_size,
            "average_utilization": average_utilization,
            "average_queue_utilization": average_queue_utilization,
        }

        metrics["aggregate"] = MetricsDict(aggregate)
        return metrics

    def _get_station_by_location(self, location: str) -> ChargingStation | None:
        """Find a charging station by its location."""
        infrastructures = self._simulation.world.charging_infrastructures
        if infrastructures is None:
            return None

        for infrastructure in infrastructures:
            for station in infrastructure.charging_stations:
                if station.location == location:
                    return station
        return None

    def _get_station_metrics(self, station: ChargingStation) -> MetricsDict:
        """Get metrics for a single charging station."""
        current_users = station.plugs.count
        current_queue_size = len(station.plugs.queue)
        capacity = station.capacity
        queue_capacity = station.queue_size

        return MetricsDict(
            {
                "current_users": current_users,
                "current_queue_size": current_queue_size,
                "current_queue_time": station.current_queue_time,
                "price_per_kWh": station.price_per_kWh,
                "utilization": current_users / capacity if capacity > 0 else 0.0,
                "queue_utilization": (
                    current_queue_size / queue_capacity if queue_capacity > 0 else 0.0
                ),
            }
        )
