from enum import Enum

from simpy import Environment

from simulation.operator.operations_management.service_tasks.service_task import ServiceTask

import logging

from simulation.operator.operations_management.task_queue import TaskQueue


class ServiceWorkerState(Enum):
    FREE = 0
    WORKING = 1
    HIBERNATE = 3

class ServiceWorker:
    service_worker_id = 0

    def __init__(self, env:Environment, task_queue:TaskQueue):
        self._id = ServiceWorker.service_worker_id

        self._env = env
        self._state = ServiceWorkerState.HIBERNATE

        self._task_queue = task_queue

        self._task_finished = self._env.event()

        ServiceWorker.service_worker_id += 1

    def run(self):

        while True:
            # Wait until operation management engine puts tasks into queue
            yield self._task_queue.task_queue_updated

            logging.debug(f"Waking up and searching for available jobs.",
                          extra={"clazz": self.__class__.__name__, "oid": self._id})

            self._state = ServiceWorkerState.FREE

            while self._task_queue.count > 0:
                next_task = self._task_queue.popleft()

                yield self._env.process(self.execute_task(next_task))

                yield next_task.task_finished

            logging.debug(f"There are no more tasks for me. Going into hibernate.",
                          extra={"clazz": self.__class__.__name__, "oid": self._id})

            # Go back to sleep
            self._state = ServiceWorkerState.HIBERNATE

    def execute_task(self, service_task: ServiceTask):
        """
        Execute assigned task
        :param service_task:
        :return:
        """
        self._state = ServiceWorkerState.WORKING

        logging.debug(f"Processing following task: {service_task}.",
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

        yield self._env.process(service_task.execute(self._id))

        self._state = ServiceWorkerState.FREE

        # Notify that service worker completed her job
        self._task_finished.succeed()
        self._task_finished = self._env.event()

    @property
    def task_finished(self):
        return self._task_finished

    @property
    def state(self):
        return self._state

