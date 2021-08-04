from simpy import Environment

from simulation.operator.operations_management.service_tasks.service_task import ServiceTask


class MultiServiceTask(ServiceTask):

    def __init__(self, env: Environment):
        super().__init__(env)

        self._service_tasks = []

    def execute(self, *args):
        events = []
        for service_task in self._service_tasks:
            events.append(service_task.task_finished)
            self._env.process(service_task.execute())

        yield self._env.all_of(events)

        self._task_finished.succeed()

    def append_task(self, service_task: ServiceTask):
        self._service_tasks.append(service_task)

    def __str__(self):
        return f"Multi Tasks with {len(self._service_tasks)} sub tasks:{self._service_tasks}"
