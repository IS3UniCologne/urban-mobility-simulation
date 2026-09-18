"""Service workforce module managing a pool of service workers and their shared job queue."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simpy import Process

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import WorkerCostConfig
    from simulation.operator.accounting import WorkerLedger

from simulation.operator.operations_management.service_jobs.job_queue import JobQueue
from simulation.operator.service_worker import ServiceWorker


class ServiceWorkforce:
    """
    Pool of service workers sharing a single job queue.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    number_service_workers : int
        Number of workers to spawn.
    cost_config : WorkerCostConfig
        Operator cost rates for every worker.
    ledger : WorkerLedger
        Ledger each worker reports to.
    """

    __slots__ = ("_job_queue", "_number_service_workers", "_service_workers", "_sim")

    def __init__(
        self,
        sim: SimulationContext,
        number_service_workers: int,
        cost_config: WorkerCostConfig,
        ledger: WorkerLedger,
    ) -> None:
        self._sim = sim
        self._service_workers: list[Process] = []
        self._job_queue = JobQueue(sim=sim)
        self._number_service_workers = number_service_workers

        for i in range(number_service_workers):
            self._service_workers.append(
                sim.env.process(
                    ServiceWorker(
                        sim=sim,
                        job_queue=self._job_queue,
                        cost_config=cost_config,
                        ledger=ledger,
                    ).run()
                )
            )

    @property
    def job_queue(self) -> JobQueue:
        """Return the shared job queue."""
        return self._job_queue

    @property
    def number_service_workers(self) -> int:
        """Return the number of workers in the pool."""
        return self._number_service_workers

    # TODO: Properties thread safe?
