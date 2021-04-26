from simulation.environment.position import Position
from simulation.tasks.transport_task import TransportTask


class TransportationSearchTask:

    def __init__(self, agent_position: Position, transport_task: TransportTask):
        self._agent_position = agent_position
        self._transport_task = transport_task

    @property
    def agent_position(self):
        pass

    @property
    def transport_task(self):
        return self._transport_task