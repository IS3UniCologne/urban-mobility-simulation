from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext

from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.operator.service_worker import ServiceWorker


class ServiceWorkforce:  # noqa: D101
    __slots__ = ("_number_service_workers", "_service_workers", "_sim", "_task_queue")

    def __init__(self, sim: SimulationContext, number_service_workers: int) -> None:
        self._sim = sim
        self._service_workers = []
        self._task_queue = TaskQueue(sim=sim)
        self._number_service_workers = number_service_workers

        for i in range(number_service_workers):
            self._service_workers.append(
                sim.env.process(
                    ServiceWorker(sim=sim, task_queue=self._task_queue).run()
                )
            )

    @property
    def task_queue(self) -> TaskQueue:  # noqa: D102
        return self._task_queue

    @property
    def number_service_workers(self) -> int:  # noqa: D102
        return self._number_service_workers

    # TODO: Properties thread safe?
