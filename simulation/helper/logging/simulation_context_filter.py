import logging


class SimulationContextFilter(logging.Filter):
    __slots__ = ("_env",)

    def __init__(self, filter_name, extra):  # noqa: ANN001, ANN204
        super(SimulationContextFilter, self).__init__(filter_name)  # noqa: UP008
        self._env = extra

    def filter(self, record):  # noqa: ANN001, ANN201
        if self._env:
            record.env_time = round(self._env.now, 2)
        else:
            record.env_time = "INIT"
        return True
