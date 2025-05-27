import logging


class ExtraDefaultFilter(logging.Filter):
    def __init__(self, filter_name):  # noqa: ANN001, ANN204
        super(ExtraDefaultFilter, self).__init__(filter_name)  # noqa: UP008

    def filter(self, record):  # noqa: ANN001, ANN201
        if not hasattr(record, "clazz"):
            record.clazz = "Unknown"

        if not hasattr(record, "oid"):
            record.oid = "-"
        return True
