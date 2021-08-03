from simulation.operator.operations_management.service_tasks.service_task import ServiceTask


class MultiServiceTask(ServiceTask):

    def __init__(self):
        self._service_tasks = []

    def execute(self, simpy_env, *args):
        for service_task in self._service_tasks:
            service_task.execute(simpy_env)

        # TODO: Does this work?
        yield simpy_env.event().succeed()

    def append_task(self, service_task: ServiceTask):
        self._service_tasks.append(service_task)