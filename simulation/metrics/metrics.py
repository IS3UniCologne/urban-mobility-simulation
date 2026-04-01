"""Main metrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

from .metrics_base import MetricsBase
from .metrics_dict import MetricsDict
from .metrics_tracker import MetricsTracker
from .providers import (
    AuctionMetrics,
    ChargingStationMetrics,
    FleetMetrics,
    OperatorMetrics,
    UserMetrics,
    WorldMetrics,
)

if TYPE_CHECKING:
    import logging

    from simulation.simulation import Simulation


class Metrics(SimulationBase):
    """
    Central metrics class for accessing and managing simulation metrics.

    This class serves as the main entry point for accessing all simulation metrics,
    coordinating between different metrics classes and providing unified access.

    Parameters
    ----------
    simulation : Simulation
        The main simulation instance.

    Attributes
    ----------
    world_metrics : WorldMetrics
        Metrics related to the simulation world.
    operator_metrics : OperatorMetrics
        Metrics related to operators.
    user_metrics : UserMetrics
        Metrics related to users.
    charging_station_metrics : ChargingStationMetrics
        Metrics related to charging stations.
    fleet_metrics : FleetMetrics
        Metrics related to fleets.
    auction_metrics : AuctionMetrics
        Metrics related to auctions.
    """

    def __init__(self, simulation: Simulation) -> None:
        super().__init__(simulation.sim)
        self._sim = simulation.sim
        # Initialize individual metrics classes
        self.world_metrics = WorldMetrics(simulation)
        self.operator_metrics = OperatorMetrics(simulation)
        self.user_metrics = UserMetrics(simulation)
        self.charging_station_metrics = ChargingStationMetrics(simulation)
        self.fleet_metrics = FleetMetrics(simulation)
        self.auction_metrics = AuctionMetrics(simulation)

        # Initialize metrics tracker
        self._tracker = MetricsTracker(simulation)

        self._metrics_classes_cache: dict[str, MetricsBase] | None = None

    @property
    def tracker(self) -> MetricsTracker:
        """
        Get the metrics tracker for time-series data collection.

        Returns
        -------
        MetricsTracker
            The metrics tracker instance.
        """
        return self._tracker

    def get_metrics_classes(self) -> dict[str, MetricsBase]:
        """
        Get all available metrics classes using introspection.

        This method dynamically retrieves all metrics classes defined in this module
        and returns them in a dictionary format. This way we don't have to hardcode
        class names or maintain a list of metrics classes.

        Returns
        -------
        dict
            Mapping of class name (str) to a metrics instance (MetricsBase).
        """
        if self._metrics_classes_cache is not None:
            return self._metrics_classes_cache

        metrics_classes = {}

        # Use introspection to find all metrics attributes
        for attr_name in dir(self):
            if attr_name.endswith("_metrics") and not attr_name.startswith("_"):
                # Convert attribute name to class name (e.g., 'world_metrics' -> 'world')
                class_name = attr_name.replace("_metrics", "")
                metrics_instance = getattr(self, attr_name)

                # Only include if it's a MetricsBase instance
                if isinstance(metrics_instance, MetricsBase):
                    metrics_classes[class_name] = metrics_instance

        self._metrics_classes_cache = metrics_classes
        return metrics_classes

    def get_available_class_names(self) -> list[str]:
        """
        Get list of available metrics class names.

        Returns
        -------
        list of str
            List of available metrics class names.
        """
        return list(self.get_metrics_classes().keys())

    def get_metrics_for_classes(self, class_names: list[str]) -> MetricsDict:
        """
        Get metrics data for specific classes.

        Parameters
        ----------
        class_names : list of str
            List of metrics class names to include.

        Returns
        -------
        MetricsDict
            A MetricsDict containing metrics for the specified classes.
        """
        result = MetricsDict()
        available_classes = self.get_metrics_classes()

        for class_name in class_names:
            try:
                metrics_instance = available_classes[class_name]
                result[class_name] = metrics_instance.to_dict()
            except Exception as e:
                self._logger.warning("Failed to get metrics for %s: %s", class_name, e)
        return result

    def all_metrics(self) -> MetricsDict:
        """
        Get all metrics from all available classes.

        Returns
        -------
        MetricsDict
            Dictionary containing all simulation metrics.
        """
        return self.get_metrics_for_classes(self.get_available_class_names())

    def to_log(self, logger: logging.Logger | None = None) -> None:
        """
        Log all metrics.

        Parameters
        ----------
        logger : logging.Logger or None
            Logger to use. If None, uses the default metrics output logger.
        """
        if logger is None:
            logger = self._sim.log_manager.get_metrics_output_logger()

        try:
            all_metrics = self.all_metrics()
            all_metrics.to_log(logger)
        except Exception as e:
            self._logger.error("Failed to log metrics: %s", e)
