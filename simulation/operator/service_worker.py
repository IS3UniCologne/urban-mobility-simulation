"""Service worker module for executing jobs from the job queue."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.operations_management.service_jobs.job_queue import (
        JobQueue,
    )
    from simulation.operator.operations_management.service_jobs.service_job import (
        ServiceJob,
    )


class ServiceWorkerState(Enum):  # noqa: D101
    FREE = 0
    WORKING = 1
    HIBERNATE = 3


class ServiceWorker(SimulationBase):  # noqa: D101
    service_worker_id = 0

    __slots__ = ("_env", "_id", "_job_queue", "_state")

    def __init__(self, sim: SimulationContext, job_queue: JobQueue) -> None:
        super().__init__(sim)

        self._env = sim.env
        self._state = ServiceWorkerState.HIBERNATE

        self._job_queue = job_queue

        ServiceWorker.service_worker_id += 1

    def run(self):  # noqa: ANN201, D102
        while True:
            # Wait until operation management engine puts jobs into queue
            yield self._job_queue.queue_updated

            self.logger.debug("Waking up and searching for available jobs.")

            self._state = ServiceWorkerState.FREE

            while self._job_queue.count > 0:
                next_job = self._job_queue.popleft()

                yield self._env.process(self.execute_job(next_job))

            self.logger.debug("No more jobs to process. Going into hibernate.")

            # Go back to sleep
            self._state = ServiceWorkerState.HIBERNATE

    def execute_job(self, job: ServiceJob):  # noqa: ANN201
        """Execute assigned service job.

        Parameters
        ----------
        job : ServiceJob
            The job to execute.
        """
        self._state = ServiceWorkerState.WORKING

        self.logger.debug("Processing following job: %s.", job)

        yield self._env.process(job.execute())

        self._state = ServiceWorkerState.FREE

    @property
    def state(self):  # noqa: ANN201, D102
        return self._state
