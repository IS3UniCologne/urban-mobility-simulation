from simulation.environment.position import Position
from simulation.tasks.transport_task import TransportTask


class TransportationSearchTask:
    __slots = ("_agent_position", "_transport_task", "_fleet")

    def __init__(self, agent_position: Position, transport_task: TransportTask, fleet):
        self._agent_position = agent_position
        self._transport_task = transport_task
        self._fleet = fleet

    @property
    def agent_position(self):
        return self._agent_position

    @property
    def transport_task(self):
        return self._transport_task

    @property
    def fleet(self):
        return self._fleet
