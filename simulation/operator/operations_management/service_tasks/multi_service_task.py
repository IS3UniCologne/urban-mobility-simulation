from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext

from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
)


class MultiServiceTask(ServiceTask):
    __slots__ = ("_service_tasks",)

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)

        self._service_tasks = []

    def execute(self, *args):  # noqa: ANN002, ANN201
        events = []
        for service_task in self._service_tasks:
            events.append(service_task.task_finished)
            self._env.process(service_task.execute(args[0]))

        yield self._env.all_of(events)

        # Notify all
        self._task_finished.succeed()

        # Notify all
        self._task_finished = self._env.event()

    def append_task(self, service_task: ServiceTask) -> None:
        self._service_tasks.append(service_task)

    def __str__(self) -> str:
        return f"Multi Tasks with {len(self._service_tasks)} sub tasks:{self._service_tasks}"
