from collections import deque

from simpy import Environment

from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
)


class TaskQueue:
    __slots__ = ("_env", "_queue", "_task_queue_updated")

    def __init__(self, env: Environment):  # noqa: ANN204
        self._env = env

        self._queue = deque()
        # Events
        self._task_queue_updated = env.event()

    def append(self, service_task: ServiceTask):  # noqa: ANN201
        self._queue.append(service_task)

        self._task_queue_updated.succeed()
        self._task_queue_updated = self._env.event()

    def bulk_append(self, service_task_list):  # noqa: ANN001, ANN201
        for service_task in service_task_list:
            self._queue.append(service_task)

        self._task_queue_updated.succeed()
        self._task_queue_updated = self._env.event()

    def popleft(self):  # noqa: ANN201
        return self._queue.popleft()

    def clear(self):  # noqa: ANN201
        self._queue.clear()

    @property
    def count(self):  # noqa: ANN201
        return len(self._queue)

    @property
    def task_queue_updated(self):  # noqa: ANN201
        return self._task_queue_updated
