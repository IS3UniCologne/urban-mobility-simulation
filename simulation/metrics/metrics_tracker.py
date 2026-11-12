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
    """
    A snapshot of metrics at a specific simulation time.

    Parameters
    ----------
    timestamp : float
        The simulation time when the snapshot was taken.
    metrics : MetricsDict
        The metrics data collected.

    Attributes
    ----------
    timestamp : float
        The simulation time when the snapshot was taken.
    metrics : MetricsDict
        The metrics data collected.
    """

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


class TrackingJob:
    """
    Represents a single tracking job.

    Parameters
    ----------
    name : str
        Job name.
    interval : float or None
        Periodic capture interval. None disables automatic periodic captures.
    tracked_classes : list of str or None
        Metrics classes to track. None means all available.

    Attributes
    ----------
    name : str
        Job name.
    interval : float or None
        Periodic capture interval.
    tracked_classes : list of str or None
        Metrics classes to track.
    process : simpy.Process or None
        The simpy process for periodic tracking, if active.
    snapshots : list of MetricsSnapshot
        List of captured snapshots.
    last_snapshot_time : float or None
        Timestamp of the last captured snapshot.
    active : bool
        Whether the job is currently active.
    """

    def __init__(
        self, name: str, interval: float | None, tracked_classes: list[str] | None
    ) -> None:
        self.name = name
        self.interval = interval
        self.tracked_classes = tracked_classes
        self.process: simpy.Process | None = None
        self.snapshots: list[MetricsSnapshot] = []
        self.last_snapshot_time: float | None = None
        self.active = False

    def add_snapshot(self, snapshot: MetricsSnapshot) -> MetricsSnapshot:
        """
        Add a snapshot to this job.

        Parameters
        ----------
        snapshot : MetricsSnapshot
            Snapshot to add.

        Returns
        -------
        MetricsSnapshot
            Added snapshot (or existing latest one if duplicate).
        """
        if (
            self.last_snapshot_time is not None
            and self.last_snapshot_time == snapshot.timestamp
            and self.snapshots
        ):
            return self.snapshots[-1]
        self.snapshots.append(snapshot)
        self.last_snapshot_time = snapshot.timestamp
        return snapshot


class MetricsTracker(SimulationBase):
    """
    Metrics tracking manager for periodic and manual snapshots.

    Can run multiple tracking jobs in parallel, each with its own configuration.

    Parameters
    ----------
    simulation : Simulation
        The main simulation instance.
    """

    def __init__(self, simulation: Simulation) -> None:
        super().__init__(simulation.sim)
        self._simulation = simulation
        self._jobs: dict[str, TrackingJob] = {}

    def create_job(
        self,
        name: str,
        interval: float | None,
        tracked_classes: list[str] | None = None,
        start_now: bool = False,
        replace: bool = False,
    ) -> TrackingJob:
        """
        Create a tracking job.

        Parameters
        ----------
        name : str
            Job name.
        interval : float or None
            Periodic capture interval. None for manual-only.
        tracked_classes : list[str] or None
            Metrics classes to track (None means all).
        start_now : bool
            Start the job immediately if True and interval is not None.
        replace : bool
            Replace existing job of the same name.

        Returns
        -------
        TrackingJob
            Created (or replaced) job.

        Raises
        ------
        ValueError
            If job exists and replace is False.
        """
        if name in self._jobs and not replace:
            raise ValueError(f"Tracking job '{name}' already exists")
        resolved_classes = (
            None
            if tracked_classes is None
            else self._resolve_tracked_classes(tracked_classes)
        )
        job = TrackingJob(name, interval, resolved_classes)
        self._jobs[name] = job
        if start_now:
            self.start_job(name)
        self._logger.info(
            "Created tracking job %s (interval=%s, classes=%s, start=%s)",
            name,
            interval,
            resolved_classes if resolved_classes is not None else "ALL",
            start_now,
        )
        return job

    def start_job(self, name: str) -> None:
        """
        Start periodic tracking for a job (no effect if already active).

        Parameters
        ----------
        name : str
            Job name.
        """
        job = self._require_job(name)
        if job.interval is None:
            self._logger.warning(
                "Job %s has no interval; cannot start periodic process", name
            )
            return
        if job.active:
            self._logger.warning("Job %s already active", name)
            return
        job.active = True
        job.process = self._simulation.sim.env.process(self._job_process(name))
        self._logger.info(
            "Started tracking job %s with interval %s and classes %s",
            name,
            job.interval,
            job.tracked_classes if job.tracked_classes is not None else "ALL",
        )

    def start_all_jobs(self) -> None:
        """Start all tracking jobs that have an interval defined."""
        for name in self._jobs.keys():
            job = self._jobs[name]
            if job.interval is not None and not job.active:
                self.start_job(name)
            else:
                self._logger.warning("Job %s already active or has no interval", name)

    def stop_job(self, name: str) -> None:
        """
        Stop a tracking job's periodic process.

        Parameters
        ----------
        name : str
            Job name.
        """
        job = self._require_job(name)
        if not job.active:
            self._logger.warning("Job %s not active", name)
            return
        job.active = False
        if job.process is not None:
            try:
                if not job.process.processed:
                    job.process.interrupt()
            except RuntimeError as e:
                self._logger.debug("Process interruption issue for job %s: %s", name, e)
            finally:
                job.process = None
        self._logger.info("Stopped tracking job %s", name)

    def stop_all_jobs(self) -> None:
        """Stop all active tracking jobs."""
        for name in self._jobs.keys():
            self.stop_job(name)

    def capture_job_snapshot(self, name: str) -> MetricsSnapshot:
        """
        Manually capture a snapshot for a job.

        Parameters
        ----------
        name : str
            Job name.

        Returns
        -------
        MetricsSnapshot
            The captured metrics snapshot.
        """
        job = self._require_job(name)
        current_time = self._simulation.sim.time
        metrics = self._collect_metrics(job.tracked_classes)
        try:
            snapshot = MetricsSnapshot(current_time, metrics)
            job.add_snapshot(snapshot)
            self._logger.debug("Captured snapshot for job %s at %s", name, current_time)
            return snapshot
        except Exception as e:
            self._logger.error("Failed capturing snapshot for job %s: %s", name, e)
            empty = MetricsSnapshot(current_time, MetricsDict())
            job.add_snapshot(empty)
            return empty

    def capture_all_job_snapshots(self) -> dict[str, MetricsSnapshot]:
        """
        Capture snapshots for all jobs.

        Returns
        -------
        dict[str, MetricsSnapshot]
            Mapping job name to snapshot.
        """
        result: dict[str, MetricsSnapshot] = {}
        for name in self._jobs.keys():
            result[name] = self.capture_job_snapshot(name)
        return result

    def get_snapshots(
        self, name: str, start_time: float | None = None, end_time: float | None = None
    ) -> list[MetricsSnapshot]:
        """
        Retrieve snapshots for a job within a time range.

        Parameters
        ----------
        name : str
            Job name.
        start_time : float or None
            Start time for filtering snapshots. If None, includes from beginning.
        end_time : float or None
            End time for filtering snapshots. If None, includes until end.

        Returns
        -------
        list of MetricsSnapshot
            List of snapshots within the specified time range.
        """
        job = self._require_job(name)
        out: list[MetricsSnapshot] = []
        for s in job.snapshots:
            if start_time is not None and s.timestamp < start_time:
                continue
            if end_time is not None and s.timestamp > end_time:
                continue
            out.append(s)
        return out

    def dataframe(
        self, name: str, start_time: float | None = None, end_time: float | None = None
    ) -> pd.DataFrame:
        """
        Convert a job's snapshots to a DataFrame.

        Parameters
        ----------
        name : str
            Job name.
        start_time : float or None
            Start filter.
        end_time : float or None
            End filter.

        Returns
        -------
        pandas.DataFrame
            DataFrame indexed by timestamp containing the job's snapshots.
        """
        snaps = self.get_snapshots(name, start_time, end_time)
        if not snaps:
            return pd.DataFrame()
        data = [s.to_dict() for s in snaps]
        df = pd.DataFrame(data)
        df = df.set_index("timestamp")
        return df

    def dataframe_all(
        self,
        start_time: float | None = None,
        end_time: float | None = None,
        long: bool = True,
    ) -> pd.DataFrame:
        """
        Combine all jobs into a single DataFrame.

        Parameters
        ----------
        start_time : float or None
            Start filter.
        end_time : float or None
            End filter.
        long : bool
            If True, returns long format with 'job' column.
            If False, returns a multi-index (job, timestamp) wide format.

        Returns
        -------
        pandas.DataFrame
            Combined DataFrame for all jobs, either in long or wide format.
        """
        frames: list[pd.DataFrame] = []
        for name in self._jobs.keys():
            df = self.dataframe(name, start_time, end_time)
            if df.empty:
                continue
            df.insert(0, "job", name)
            frames.append(df.reset_index())
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        if long:
            return combined
        combined = combined.set_index(["job", "timestamp"])
        return combined

    def export_job(
        self,
        name: str,
        file_name: str,
        start_time: float | None = None,
        end_time: float | None = None,
        file_format: str = "csv",
    ) -> None:
        """
        Export a single job's snapshots.

        Parameters
        ----------
        name : str
            Job name.
        file_name : str
            Base file name.
        start_time : float or None
            Start time filter.
        end_time : float or None
            End time filter.
        file_format : str
            Format of the output file (e.g., "csv", "parquet").
        """
        df = self.dataframe(name, start_time, end_time)
        if df.empty:
            self._logger.warning("No snapshots to export for job %s", name)
            return
        if not file_name.endswith(f".{file_format}"):
            file_name = f"{file_name}.{file_format}"
        timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        base, ext = os.path.splitext(file_name)
        final_name = f"{base}_{name}_{timestamp}{ext}"
        dir_path = os.path.dirname("data/output/" + "metrics_tracking/")
        os.makedirs(dir_path, exist_ok=True)
        full_path = os.path.join(dir_path, final_name)
        if file_format == "csv":
            df.to_csv(full_path)
        elif file_format == "parquet":
            df.to_parquet(full_path)
        else:
            self._logger.error("Unsupported file format: %s", file_format)
            return
        self._logger.info(
            "Exported %d snapshots for job %s to %s", len(df), name, full_path
        )

    def export_all_jobs(
        self,
        file_name: str,
        start_time: float | None = None,
        end_time: float | None = None,
        file_format: str = "csv",
    ) -> None:
        """
        Export all jobs' snapshots one by one.

        Parameters
        ----------
        file_name : str
            Base file name used for each job.
        start_time : float or None
            Start filter.
        end_time : float or None
            End filter.
        file_format : str
            Export format.
        """
        for name in self._jobs.keys():
            self.export_job(name, file_name, start_time, end_time, file_format)

    def clear_snapshots(self, name: str | None = None) -> None:
        """
        Clear snapshots for one or all jobs.

        Parameters
        ----------
        name : str or None
            Job name or None for all.
        """
        if name is None:
            total = sum(len(j.snapshots) for j in self._jobs.values())
            for j in self._jobs.values():
                j.snapshots.clear()
                j.last_snapshot_time = None
            self._logger.info("Cleared %d snapshots across all jobs", total)
            return
        job = self._require_job(name)
        count = len(job.snapshots)
        job.snapshots.clear()
        job.last_snapshot_time = None
        self._logger.info("Cleared %d snapshots for job %s", count, name)

    def _require_job(self, name: str) -> TrackingJob:
        job = self._jobs.get(name)
        if job is None:
            raise ValueError(f"Unknown tracking job '{name}'")
        return job

    def _resolve_tracked_classes(self, classes: list[str]) -> list[str]:
        def normalize(n: str) -> str:
            n = n.lower().replace("_", "")
            if n.endswith("metrics"):
                n = n[:-7]
            return n

        available = self._simulation.metrics.get_metrics_classes()
        normalized = {normalize(k): k for k in available.keys()}
        resolved: list[str] = []
        invalid: list[str] = []
        for c in classes:
            n = normalize(c)
            if n in normalized:
                resolved.append(normalized[n])
            else:
                invalid.append(c)
        if invalid:
            raise ValueError(
                f"Unknown metrics class(es) {invalid}. Available: {list(available.keys())}"
            )
        return resolved

    def _collect_metrics(self, classes: list[str] | None) -> MetricsDict:
        """
        Collect metrics for the given classes without caching.

        Parameters
        ----------
        classes : list[str] or None
            Metrics class names to include; None means all classes.

        Returns
        -------
        MetricsDict
            Collected metrics for the specified classes.
        """
        if classes is None:
            return self._simulation.metrics.all_metrics()
        return self._simulation.metrics.get_metrics_for_classes(list(classes))

    def _job_process(self, name: str) -> Generator[Any, None, None]:
        job = self._require_job(name)
        try:
            if job.interval is not None:
                yield self._simulation.sim.env.timeout(job.interval)
            while job.active and job.interval is not None:
                self.capture_job_snapshot(name)
                yield self._simulation.sim.env.timeout(job.interval)
        except Exception as e:
            if job.active:
                self._logger.error("Error in tracking job %s process: %s", name, e)
                job.active = False
