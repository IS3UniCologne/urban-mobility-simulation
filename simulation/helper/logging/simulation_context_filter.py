import logging


class SimulationContextFilter(logging.Filter):
    def __init__(self, filter_name, extra):
        super(SimulationContextFilter, self).__init__(filter_name)
        self._env = extra

    def filter(self, record):
        record.env_time = self._env.now
        return True