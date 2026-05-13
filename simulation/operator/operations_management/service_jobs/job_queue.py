"""Job queue for service jobs dispatched to service workers."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.operations_management.service_jobs.service_job import (
        ServiceJob,
    )


class JobQueue:  # noqa: D101
    __slots__ = ("_env", "_queue", "_queue_updated", "_sim")

    def __init__(self, sim: SimulationContext) -> None:
        self._sim = sim
        self._env = sim.env

        self._queue: deque[ServiceJob] = deque()
        self._queue_updated = self._env.event()

    def append(self, job: ServiceJob) -> None:  # noqa: D102
        self._queue.append(job)

        self._queue_updated.succeed()
        self._queue_updated = self._env.event()

    def bulk_append(self, jobs: list[ServiceJob]) -> None:  # noqa: D102
        for job in jobs:
            self._queue.append(job)

        self._queue_updated.succeed()
        self._queue_updated = self._env.event()

    def popleft(self) -> ServiceJob:  # noqa: D102
        return self._queue.popleft()

    def clear(self) -> None:  # noqa: D102
        self._queue.clear()

    @property
    def count(self) -> int:  # noqa: D102
        return len(self._queue)

    @property
    def queue_updated(self) -> Event:  # noqa: D102
        return self._queue_updated
