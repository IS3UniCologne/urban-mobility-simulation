from simulation.environment.position import Position


class VehicleSearchTask:

    def __init__(self, agent_position: Position):
        self._agent_position = agent_position

    @property
    def agent_position(self):
        pass

    @agent_position.setter
    def agent_position(self, position: Position):
        self._agent_position = position