"""Service worker module for executing jobs from the job queue."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import WorkerCostConfig
    from simulation.operator.cost_accounting import WorkerCostReporter
    from simulation.operator.operations_management.service_jobs.job_queue import (
        JobQueue,
    )
    from simulation.operator.operations_management.service_jobs.service_job import (
        ServiceJob,
    )


class ServiceWorkerState(Enum):
    """Lifecycle states of a service worker."""

    FREE = 0
    WORKING = 1
    HIBERNATE = 3

    @property
    def on_duty(self) -> bool:
        """Whether worker time is paid in this state."""
        return self is not ServiceWorkerState.HIBERNATE


class ServiceWorker(SimulationBase):
    """
    Worker process that executes service jobs from a shared queue.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    job_queue : JobQueue
        Queue supplying jobs to execute.
    cost_config : WorkerCostConfig
        Operator cost rates for this worker.
    cost_reporter : WorkerCostReporter
        Sink for cost-relevant quantities.
    """

    service_worker_id: ClassVar[int] = 0  # TODO: not thread safe

    __slots__ = ("_cost_config", "_cost_reporter", "_env", "_job_queue", "_state")

    def __init__(
        self,
        sim: SimulationContext,
        job_queue: JobQueue,
        cost_config: WorkerCostConfig,
        cost_reporter: WorkerCostReporter,
    ) -> None:
        super().__init__(sim)

        self._env = sim.env
        self._state = ServiceWorkerState.HIBERNATE

        self._job_queue = job_queue

        self._cost_config = cost_config
        self._cost_reporter = cost_reporter
        self._cost_reporter.register_worker(self, active=self._state.on_duty)

        ServiceWorker.service_worker_id += 1

    @property
    def cost_config(self) -> WorkerCostConfig:
        """Operator cost rates for this worker."""
        return self._cost_config

    def run(self):  # noqa: ANN201, D102
        while True:
            # Wait until operation management engine puts jobs into queue
            yield self._job_queue.queue_updated

            self.logger.debug("Waking up and searching for available jobs.")

            self._set_state(ServiceWorkerState.FREE)

            while self._job_queue.count > 0:
                next_job = self._job_queue.popleft()

                yield self._env.process(self.execute_job(next_job))

            self.logger.debug("No more jobs to process. Going into hibernate.")

            # Go back to sleep
            self._set_state(ServiceWorkerState.HIBERNATE)

    def execute_job(self, job: ServiceJob) -> Generator[Event, None, None]:
        """Execute assigned service job.

        Parameters
        ----------
        job : ServiceJob
            Job to execute.

        Yields
        ------
        Event
            Job execution process.
        """
        self._set_state(ServiceWorkerState.WORKING)

        self.logger.debug("Processing following job: %s.", job)

        yield self._env.process(job.execute())

        self._set_state(ServiceWorkerState.FREE)

    def _set_state(self, state: ServiceWorkerState) -> None:
        """Transition to a new state and report activity for cost accounting."""
        if state is self._state:
            return
        self._state = state
        self._cost_reporter.set_worker_active(self, active=state.on_duty)

    @property
    def state(self) -> ServiceWorkerState:
        """Return the current worker state."""
        return self._state
