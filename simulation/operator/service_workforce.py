from simpy import Environment

from simulation.operator.operations_management.task_queue import TaskQueue
from simulation.operator.service_worker import ServiceWorker


class ServiceWorkforce:

    __slots__ = ("_service_workers", "_task_queue", "_number_service_workers")
    
    def __init__(self, env: Environment, number_service_workers: int):
        self._service_workers = []
        self._task_queue = TaskQueue(env=env)
        self._number_service_workers = number_service_workers

        for i in range(number_service_workers):
            self._service_workers.append(
                env.process(ServiceWorker(env=env, task_queue=self._task_queue).run())
            )

    @property
    def task_queue(self):
        return self._task_queue

    @property
    def number_service_workers(self):
        return self._number_service_workers

    # TODO: Properties thread safe?
