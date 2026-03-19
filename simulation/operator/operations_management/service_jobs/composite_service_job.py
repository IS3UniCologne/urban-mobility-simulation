"""Composite service job that executes multiple sub-jobs in parallel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.operator.operations_management.service_jobs.service_job import (
    ServiceJob,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext


class CompositeServiceJob(ServiceJob):
    """Executes multiple sub-jobs in parallel."""

    __slots__ = ("_sub_jobs",)

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._sub_jobs: list[ServiceJob] = []

    def execute(self) -> Generator[Event, None, None]:
        """Execute all sub-jobs in parallel and wait for completion."""
        events = []
        for job in self._sub_jobs:
            events.append(job.finished)
            self._env.process(job.execute())

        yield self._env.all_of(events)

        self._finished.succeed()

    def append_job(self, job: ServiceJob) -> None:
        """Add a sub-job to be executed in parallel."""
        self._sub_jobs.append(job)

    def __str__(self) -> str:  # noqa: D105
        return (
            f"CompositeServiceJob with {len(self._sub_jobs)} sub-jobs: {self._sub_jobs}"
        )
