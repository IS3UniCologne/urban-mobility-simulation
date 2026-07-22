"""Service workforce module managing a pool of service workers and their shared job queue."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import WorkerCostConfig
    from simulation.operator.cost_accounting import WorkerCostReporter

from simulation.operator.cost_accounting import NULL_WORKER_COST_REPORTER
from simulation.operator.operations_management.service_jobs.job_queue import JobQueue
from simulation.operator.service_worker import ServiceWorker


class ServiceWorkforce:  # noqa: D101
    __slots__ = ("_job_queue", "_number_service_workers", "_service_workers", "_sim")

    def __init__(
        self,
        sim: SimulationContext,
        number_service_workers: int,
        cost_config: WorkerCostConfig,
        cost_reporter: WorkerCostReporter = NULL_WORKER_COST_REPORTER,
    ) -> None:
        self._sim = sim
        self._service_workers = []
        self._job_queue = JobQueue(sim=sim)
        self._number_service_workers = number_service_workers

        for i in range(number_service_workers):
            self._service_workers.append(
                sim.env.process(
                    ServiceWorker(
                        sim=sim,
                        job_queue=self._job_queue,
                        cost_config=cost_config,
                        cost_reporter=cost_reporter,
                    ).run()
                )
            )

    @property
    def job_queue(self) -> JobQueue:  # noqa: D102
        return self._job_queue

    @property
    def number_service_workers(self) -> int:  # noqa: D102
        return self._number_service_workers

    # TODO: Properties thread safe?
