"""Main metrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

from .metrics_dict import MetricsDict
from .metrics_tracker import MetricsTracker
from .operator_metrics import OperatorMetrics
from .world_metrics import WorldMetrics

if TYPE_CHECKING:
    import logging

    from simulation.simulation import Simulation

    from .metrics_base import MetricsBase


class Metrics(SimulationBase):
    """
    Central metrics class for accessing and managing simulation metrics.

    This class serves as the main entry point for accessing all simulation metrics,
    coordinating between different metrics classes and providing unified access.
    """

    def __init__(self, simulation: Simulation) -> None:
        super().__init__(simulation.sim)
        self._sim = simulation.sim
        # Initialize individual metrics classes
        self.world_metrics = WorldMetrics(simulation)
        self.operator_metrics = OperatorMetrics(simulation)

        # Initialize metrics tracker
        self._tracker = MetricsTracker(simulation)

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
        dict[str, MetricsBase]
            Dictionary mapping class names to metrics instances.
        """
        metrics_classes = {}

        # Use introspection to find all metrics attributes
        for attr_name in dir(self):
            if attr_name.endswith("_metrics") and not attr_name.startswith("_"):
                # Convert attribute name to class name (e.g., 'world_metrics' -> 'world')
                class_name = attr_name.replace("_metrics", "")
                metrics_instance = getattr(self, attr_name)

                # Only include if it's a MetricsBase instance
                if hasattr(metrics_instance, "to_dict") and hasattr(
                    metrics_instance, "to_log"
                ):
                    metrics_classes[class_name] = metrics_instance

        return metrics_classes

    def get_available_class_names(self) -> list[str]:
        """
        Get list of available metrics class names.

        Returns
        -------
        list[str]
            List of available metrics class names.
        """
        return list(self.get_metrics_classes().keys())

    def get_metrics_for_classes(self, class_names: list[str]) -> MetricsDict:
        """
        Get metrics data for specific classes.

        Parameters
        ----------
        class_names : list[str]
            List of metrics class names to include.

        Returns
        -------
        MetricsDict
            Dictionary containing metrics from specified classes.
        """
        result = MetricsDict()
        available_classes = self.get_metrics_classes()

        for class_name in class_names:
            if class_name in available_classes:
                try:
                    metrics_instance = available_classes[class_name]
                    result[class_name] = metrics_instance.to_dict()
                except Exception as e:
                    # Log warning but continue with other classes
                    self._logger.warning(
                        "Failed to get metrics for %s: %s", class_name, e
                    )
            else:
                available = list(available_classes.keys())
                self._logger.warning(
                    "Unknown metrics class '%s'. Available: %s", class_name, available
                )

        return result

    def all_metrics(self) -> MetricsDict:
        """
        Get all metrics from all available classes.

        Returns
        -------
        MetricsDict
            Dictionary containing all simulation metrics.
        """
        result = MetricsDict()
        available_classes = self.get_metrics_classes()

        for class_name, metrics_instance in available_classes.items():
            try:
                result[class_name] = metrics_instance.to_dict()
            except Exception as e:
                self._logger.error(
                    "Failed to collect metrics from %s: %s", class_name, e
                )

        return result

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
