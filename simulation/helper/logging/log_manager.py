"""
LogManager for centralized logging setup.

This class encapsulates all logging configuration, including formatters, handlers, log levels, and filters.
"""

import logging
import os
from datetime import datetime
from logging.handlers import MemoryHandler

import simpy

from simulation.helper.configuration.configuration import Configuration
from simulation.helper.logging.extra_default_filter import ExtraDefaultFilter
from simulation.helper.logging.simulation_context_filter import SimulationContextFilter


class LogManager:
    """
    Centralized logging manager.

    Methods
    -------
    setup_logging(config, env=None):
        Set up logging with the given configuration and optional SimPy environment.
    """

    @staticmethod
    def setup_logging(config: Configuration, env: simpy.Environment) -> None:
        """
        Set up logging configuration for the simulation.

        Parameters
        ----------
        config : Configuration
            The configuration object containing logging settings and paths.
        env : simpy.Environment or None
            The simulation environment, used for env_time in logs.
        """
        # Remove all handlers from the root logger so that we can set up our own
        logging.getLogger().handlers.clear()
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Block third-party loggers
        logging.getLogger("fiona").setLevel(logging.WARNING)

        formatter = logging.Formatter(
            "[%(levelname)s] [Time %(env_time)10s] [%(clazz)30s %(oid)3s]: %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(config.settings.LOG_LEVEL)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler with MemoryHandler for buffering
        output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        logs_dir = os.path.normpath(os.path.join(config.path.OUTPUT_FOLDER, "logs"))
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        log_file = os.path.join(logs_dir, f"{output_timestamp}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(config.settings.FILE_LOG_LEVEL)
        # Buffer up to 1000 records, flush on ERROR or higher
        memory_handler = MemoryHandler(
            capacity=1000, flushLevel=logging.ERROR, target=file_handler
        )
        logger.addHandler(memory_handler)

        # Add filters
        edf = ExtraDefaultFilter(filter_name="add_default_value")
        logger.addFilter(edf)
        cf = SimulationContextFilter(filter_name="add_env", extra=env)
        logger.addFilter(cf)
