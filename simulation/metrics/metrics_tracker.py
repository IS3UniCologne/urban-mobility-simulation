"""Metrics tracking for periodic and irregular metric snapshots."""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from simulation.helper.simulation_base import SimulationBase

from .metrics_dict import MetricsDict

if TYPE_CHECKING:
    from collections.abc import Generator

    import simpy

    from simulation.simulation import Simulation


class MetricsSnapshot:
    """A snapshot of metrics at a specific simulation time."""

    def __init__(self, timestamp: float, metrics: MetricsDict) -> None:
        self.timestamp = timestamp
        self.metrics = metrics

    def to_dict(self) -> dict[str, Any]:
        """
        Convert snapshot to dictionary format.

        Returns
        -------
        dict[str, Any]
            Dictionary with timestamp and flattened metrics.
        """
        result: dict[str, Any] = {"timestamp": self.timestamp}
        result.update(self.metrics.flatten())
        return result


class MetricsTracker(SimulationBase):
    """
    Tracks simulation metrics over time with (periodic) collection.

    This class captures metrics snapshots at selected intervals and stores them
    for later analysis. It can track specific metrics classes or all available metrics.
    """

    def __init__(self, simulation: Simulation) -> None:
        super().__init__(simulation.sim)
        self._simulation = simulation

        self._snapshots: list[MetricsSnapshot] = []

        self._tracking_interval: float | None = None
        self._tracking_process: simpy.Process | None = None
        self._is_tracking = False

        self._last_snapshot_time: float | None = None

        self._tracked_classes: list[str] | None = None

    @property
    def is_tracking(self) -> bool:
        """
        Check if tracking is currently active.

        Returns
        -------
        bool
            True if tracking is active, False otherwise.
        """
        return self._is_tracking

    @property
    def tracked_classes(self) -> list[str] | None:
        """
        Get the currently tracked metrics classes.

        This will always return the classes that are currently set for tracking,
        regardless of whether tracking is active or not.

        Returns
        -------
        list[str] or None
            List of tracked class names.
        """
        if self._tracked_classes is None:
            return list(self._simulation.metrics.get_metrics_classes().keys())
        return self._tracked_classes

    def start_tracking(
        self, interval: float, tracked_classes: list[str] | None = None
    ) -> None:
        """
        Start tracking metrics.

        Parameters
        ----------
        interval : float
            Time interval between snapshots (in simulation time units).
        tracked_classes : list[str] or None
            Override the tracked classes for this tracking session.
            If None, uses the currently set tracked classes. (all by default)

        Raises
        ------
        ValueError
            If any of the specified classes don't exist in the available metrics classes.
        """
        if self._is_tracking:
            self._logger.warning("Periodic tracking is already active")
            return

        if tracked_classes is not None:
            self.set_tracked_classes(tracked_classes)

        self._tracking_interval = interval
        self._is_tracking = True

        self._tracking_process = self._simulation.sim.env.process(
            self._periodic_tracking_process()
        )

        tracked = (
            f"for classes {self._tracked_classes}"
            if self._tracked_classes
            else "for all classes"
        )
        self._logger.info(
            "Started periodic metrics tracking with interval %s %s", interval, tracked
        )

    def stop_tracking(self) -> None:
        """Stop periodic metrics tracking."""
        if not self._is_tracking:
            self._logger.warning("Periodic tracking is not active")
            return

        self._is_tracking = False

        if self._tracking_process is not None:
            try:
                if not self._tracking_process.processed:
                    self._tracking_process.interrupt()
            except RuntimeError as e:
                self._logger.debug("Tracking process not found: %s", e)
            finally:
                self._tracking_process = None

        self._logger.info("Stopped periodic metrics tracking")

    def capture_snapshot(self) -> MetricsSnapshot:
        """
        Capture a metrics snapshot at the current simulation time.

        This method is used for periodic tracking, but can also be called manually
        to capture a snapshot at any time.

        Returns
        -------
        MetricsSnapshot
            The captured metrics snapshot.
        """
        current_time = self._simulation.sim.time

        # Avoid duplicate snapshots
        if (
            self._last_snapshot_time is not None
            and current_time == self._last_snapshot_time
        ):
            self._logger.debug("Skipping duplicate snapshot at time %s", current_time)
            return self._snapshots[-1]

        try:
            if self._tracked_classes:
                metrics = self._simulation.metrics.get_metrics_for_classes(
                    self._tracked_classes
                )
            else:
                metrics = self._simulation.metrics.all_metrics()

            snapshot = MetricsSnapshot(current_time, metrics)

            self._snapshots.append(snapshot)
            self._last_snapshot_time = current_time

            self._logger.debug("Captured metrics snapshot at time %s", current_time)

            return snapshot

        except Exception as e:
            self._logger.error(
                "Failed to capture metrics snapshot at time %s: %s", current_time, e
            )
            # Create an empty snapshot to maintain consistency
            empty_snapshot = MetricsSnapshot(current_time, MetricsDict())
            return empty_snapshot

    def set_tracked_classes(self, tracked_classes: list[str] | None) -> None:
        """
        Set the list of tracked metrics classes.

        This also validates that the specified classes exist in the available metrics classes.

        Parameters
        ----------
        tracked_classes : list[str] or None
            List of classes to track. If None, tracks all classes.

        Raises
        ------
        ValueError
            If any of the specified classes don't exist in the available metrics classes.
        """

        # normalize names for more flexible matching (e.g. "WorldMetrics" vs "world" or "world_metrics")
        def normalize(name: str) -> str:
            name = name.lower().replace("_", "")
            if name.endswith("metrics"):
                name = name[:-7]
            return name

        available_classes = self._simulation.metrics.get_metrics_classes()
        normalized_available = {normalize(k): k for k in available_classes.keys()}

        if tracked_classes:
            resolved = []
            invalid = []
            for cls in tracked_classes:
                norm = normalize(cls)
                if norm in normalized_available:
                    resolved.append(normalized_available[norm])
                else:
                    invalid.append(cls)
            if invalid:
                available = list(available_classes.keys())
                raise ValueError(
                    f"Unknown metrics class(es) '{', '.join(invalid)}'. "
                    f"Available: {available}"
                )
            self._tracked_classes = resolved
            self._logger.info("Set tracked classes to: %s", ", ".join(resolved))
        else:
            self._tracked_classes = None
            self._logger.info("Set to track all metrics classes")

    def get_snapshots(
        self, start_time: float | None = None, end_time: float | None = None
    ) -> list[MetricsSnapshot]:
        """
        Get snapshots within a time range.

        Parameters
        ----------
        start_time : float or None
            Start time for filtering snapshots. If None, includes from beginning.
        end_time : float or None
            End time for filtering snapshots. If None, includes until end.

        Returns
        -------
        list[MetricsSnapshot]
            List of snapshots within the specified time range.
        """
        filtered_snapshots = []

        for snapshot in self._snapshots:
            if start_time is not None and snapshot.timestamp < start_time:
                continue
            if end_time is not None and snapshot.timestamp > end_time:
                continue
            filtered_snapshots.append(snapshot)

        return filtered_snapshots

    def to_dataframe(
        self, start_time: float | None = None, end_time: float | None = None
    ) -> pd.DataFrame:
        """
        Convert snapshots to a pandas DataFrame.

        This is also used as an intermediate step for exporting to files.

        Parameters
        ----------
        start_time : float or None
            Start time for filtering snapshots. If None, includes from beginning.
        end_time : float or None
            End time for filtering snapshots. If None, includes until end.

        Returns
        -------
        pd.DataFrame
            DataFrame with timestamps as index and metrics as columns.
        """
        snapshots = self.get_snapshots(start_time, end_time)

        if not snapshots:
            return pd.DataFrame()

        data = [snapshot.to_dict() for snapshot in snapshots]

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)

        return df

    def to_file(
        self,
        file_name: str,
        start_time: float | None = None,
        end_time: float | None = None,
        file_format: str = "csv",
    ) -> None:
        """
        Export metrics time series to a file. Defaults to CSV format, but can also export to Parquet.

        Parameters
        ----------
        filepath : str
            Path to save the file.
        start_time : float | None
            Start time for filtering snapshots. If None, includes from beginning.
        end_time : float | None
            End time for filtering snapshots. If None, includes until end.
        file_format : str
            Format of the output file (e.g., "csv", "parquet").
        """
        try:
            if not file_name.endswith(f".{file_format}"):
                file_name += f".{file_format}"

            output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
            name_without_ext, ext = os.path.splitext(file_name)
            file_name = f"{name_without_ext}_{output_timestamp}{ext}"

            file_path = os.path.dirname("data/output/" + "metrics_tracking/")
            os.makedirs(file_path, exist_ok=True)

            full_path = os.path.join(file_path, file_name)

            df = self.to_dataframe(start_time, end_time)

            if file_format == "csv":
                df.to_csv(full_path)
            elif file_format == "parquet":
                df.to_parquet(full_path)
            else:
                self._logger.error("Unsupported file format: %s", file_format)
                return

            self._logger.info("Exported %d snapshots to %s", len(df), full_path)
        except Exception as e:
            self._logger.error("Failed to export metrics to file %s: %s", file_name, e)

    def clear_snapshots(self) -> None:
        """Clear all stored snapshots."""
        snapshot_count = len(self._snapshots)
        self._snapshots.clear()
        self._last_snapshot_time = None
        self._logger.info("Cleared %d snapshots", snapshot_count)

    def _periodic_tracking_process(self) -> Generator[Any, None, None]:
        """Provide internal SimPy process for periodic tracking."""
        try:
            # Skip the first interval to allow simulation to start
            if self._tracking_interval is not None:
                yield self._simulation.sim.env.timeout(self._tracking_interval)

            # Start the periodic loop with snapshots
            while self._is_tracking and self._tracking_interval is not None:
                self.capture_snapshot()
                yield self._simulation.sim.env.timeout(self._tracking_interval)

        except Exception as e:
            if self._is_tracking:
                self._logger.error("Error in periodic tracking process: %s", e)
