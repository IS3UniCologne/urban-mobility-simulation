import logging


class SimulationContextFilter(logging.Filter):
    def __init__(self, filter_name, extra):
        super(SimulationContextFilter, self).__init__(filter_name)
        self._env = extra

    def filter(self, record):
        record.env_time = round(self._env.now, 2)
        return True