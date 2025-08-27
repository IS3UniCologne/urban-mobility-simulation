from __future__ import annotations  # noqa: D100

from enum import Enum
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.operations_management.service_tasks.service_task import (
        ServiceTask,
    )
    from simulation.operator.operations_management.task_queue import TaskQueue


class ServiceWorkerState(Enum):  # noqa: D101
    FREE = 0
    WORKING = 1
    HIBERNATE = 3


class ServiceWorker(SimulationBase):  # noqa: D101
    service_worker_id = 0

    __slots__ = ("_env", "_id", "_state", "_task_finished", "_task_queue")

    def __init__(self, sim: SimulationContext, task_queue: TaskQueue) -> None:
        super().__init__(sim)

        self._env = sim.env
        self._state = ServiceWorkerState.HIBERNATE

        self._task_queue = task_queue

        self._task_finished = self._env.event()

        ServiceWorker.service_worker_id += 1

    def run(self):  # noqa: ANN201, D102
        while True:
            # Wait until operation management engine puts tasks into queue
            yield self._task_queue.task_queue_updated

            self.logger.debug("Waking up and searching for available jobs.")

            self._state = ServiceWorkerState.FREE

            while self._task_queue.count > 0:
                next_task = self._task_queue.popleft()

                yield self._env.process(self.execute_task(next_task))

            self.logger.debug("There are no more tasks for me. Going into hibernate.")

            # Go back to sleep
            self._state = ServiceWorkerState.HIBERNATE

    def execute_task(self, service_task: ServiceTask):  # noqa: ANN201
        """
        Execute assigned task
        :param service_task:
        :return:
        """  # noqa: D205, D400
        self._state = ServiceWorkerState.WORKING

        self.logger.debug("Processing following task: %s.", service_task)

        yield self._env.process(service_task.execute(self.uid))

        self._state = ServiceWorkerState.FREE

        # Notify that service worker completed her job
        self._task_finished.succeed()
        self._task_finished = self._env.event()

    @property
    def task_finished(self):  # noqa: ANN201, D102
        return self._task_finished

    @property
    def state(self):  # noqa: ANN201, D102
        return self._state
