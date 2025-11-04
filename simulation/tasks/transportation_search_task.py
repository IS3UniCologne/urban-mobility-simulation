from simulation.environment.position import Position  # noqa: D100
from simulation.tasks.transport_task import TransportTask


class TransportationSearchTask:  # noqa: D101
    __slots = ("_agent_position", "_transport_task", "_fleet")

    def __init__(self, agent_position: Position, transport_task: TransportTask, fleet):  # noqa: ANN001, ANN204
        self._agent_position = agent_position
        self._transport_task = transport_task
        self._fleet = fleet

    @property
    def agent_position(self):  # noqa: ANN201, D102
        return self._agent_position

    @property
    def transport_task(self):  # noqa: ANN201, D102
        return self._transport_task

    @property
    def fleet(self):  # noqa: ANN201, D102
        return self._fleet
