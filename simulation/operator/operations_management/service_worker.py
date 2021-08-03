from enum import Enum

from simpy import Environment

from simulation.operator.operations_management.service_tasks.service_task import ServiceTask


class ServiceWorkerState(Enum):
    FREE = 0
    WORKING = 1

class ServiceWorker:
    service_worker_id = 0

    def __init__(self, env:Environment):
        self._id = ServiceWorker.service_worker_id

        self._env = env
        self._state = ServiceWorkerState.FREE

        self._task_finished = self._env.event()

    def execute_task(self, service_task: ServiceTask):
        """
        Execute assigned task
        :param service_task:
        :return:
        """
        self._state = ServiceWorkerState.WORKING

        self._env.process(service_task.execute(self._env))

        self._state = ServiceWorkerState.FREE

        # Notify that service worker is free again
        yield self._task_finished.succeed()
        self._task_finished = self._env.event()

    @property
    def task_finished(self):
        return self._task_finished

    @property
    def state(self):
        return self._state

