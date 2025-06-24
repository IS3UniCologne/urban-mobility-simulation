from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.operations_management.service_tasks.service_task import (
        ServiceTask,
    )


class TaskQueue:
    __slots__ = ("_env", "_queue", "_sim", "_task_queue_updated")

    def __init__(self, sim: SimulationContext) -> None:
        self._sim = sim
        self._env = sim.env

        self._queue = deque()
        # Events
        self._task_queue_updated = self._env.event()

    def append(self, service_task: ServiceTask) -> None:
        self._queue.append(service_task)

        self._task_queue_updated.succeed()
        self._task_queue_updated = self._env.event()

    def bulk_append(self, service_task_list) -> None:  # noqa: ANN001
        for service_task in service_task_list:
            self._queue.append(service_task)

        self._task_queue_updated.succeed()
        self._task_queue_updated = self._env.event()

    def popleft(self):  # noqa: ANN201
        return self._queue.popleft()

    def clear(self) -> None:
        self._queue.clear()

    @property
    def count(self) -> int:
        return len(self._queue)

    @property
    def task_queue_updated(self):  # noqa: ANN201
        return self._task_queue_updated
