"""
LogManager for centralized logging setup.

This class encapsulates all logging configuration, including formatters, handlers, log levels, and filters.
"""

from __future__ import annotations

import atexit
import logging
import os
from datetime import datetime
from logging.handlers import MemoryHandler
from typing import TYPE_CHECKING

from simulation.helper.logging.extra_default_filter import UidInjector
from simulation.helper.logging.simulation_context_filter import EnvTimeInjector

if TYPE_CHECKING:
    import simpy

    from simulation.helper.configuration.configuration import Configuration
    from simulation.helper.logging.uid_logger_adapter import UidLoggerAdapter
    from simulation.helper.types import SimId


class LogManager:
    """
    Centralized logging manager for simulation logging.

    This class manages all logging configuration including formatters, handlers,
    log levels, and filters. It provides methods to get loggers for specific
    classes and creates logger adapters with automatic UID injection.
    """

    def __init__(self, config: Configuration, env: simpy.Environment) -> None:
        """
        Initialize LogManager with configuration and simulation environment.

        Parameters
        ----------
        config : Configuration
            The configuration object containing logging settings and paths.
        env : simpy.Environment
            The simulation environment, used for env_time in logs.
        """
        self._loggers: dict[str, logging.Logger] = {}
        self._config = config
        self._class_overrides = config.settings.LOG_CLASS_OVERRIDES or {}
        self._formatter = self._create_formatter(config)

        self._create_shared_handlers(config)

        # Configure root logger
        logging.getLogger().handlers.clear()
        logger = logging.getLogger()

        console_level = getattr(logging, config.settings.LOG_LEVEL)
        file_level = getattr(logging, config.settings.FILE_LOG_LEVEL)
        logger.setLevel(min(console_level, file_level))

        # Suppress verbose third-party loggers
        logging.getLogger("fiona").setLevel(logging.WARNING)
        logging.getLogger("pyomo").setLevel(logging.WARNING)

        logger.addHandler(self._shared_console_handler)
        logger.addHandler(self._shared_memory_handler)

        # Create and configure filters
        self._uid_injector = UidInjector(filter_name="add_default_value")
        self._env_time_injector = EnvTimeInjector(filter_name="add_env", env=env)

        logger.addFilter(self._uid_injector)
        logger.addFilter(self._env_time_injector)

    def get_class_logger(self, cls_name: str) -> logging.Logger:
        """
        Get or create a logger for a specific class.

        Loggers are created on demand and share console and file handlers.
        If the class has a log level override, it uses separate handlers set to DEBUG level
        to avoid interference with the default logging behavior.

        Parameters
        ----------
        cls_name : str
            The name of the class to get a logger for.

        Returns
        -------
        logging.Logger
            The logger instance for the specified class.
        """
        if cls_name not in self._loggers:
            logger = logging.getLogger(cls_name)
            logger.propagate = False

            if cls_name in self._class_overrides:
                logger.addHandler(self._override_console_handler)
                logger.addHandler(self._override_memory_handler)

                override_level_str = self._class_overrides[cls_name]
                override_level = getattr(logging, override_level_str.upper())
                logger.setLevel(override_level)
            else:
                logger.addHandler(self._shared_console_handler)
                logger.addHandler(self._shared_memory_handler)

                console_level = getattr(logging, self._config.settings.LOG_LEVEL)
                file_level = getattr(logging, self._config.settings.FILE_LOG_LEVEL)
                logger.setLevel(min(console_level, file_level))

            logger.addFilter(self._uid_injector)
            logger.addFilter(self._env_time_injector)

            self._loggers[cls_name] = logger

        return self._loggers[cls_name]

    def get_uid_logger(self, uid: SimId) -> UidLoggerAdapter:
        """
        Get a logger adapter that automatically includes UID in all log records.

        Parameters
        ----------
        uid : SimId
            The unique identifier to include in all log records.

        Returns
        -------
        UidLoggerAdapter
            The logger adapter instance that automatically adds UID context.
        """
        from simulation.helper.logging.uid_logger_adapter import UidLoggerAdapter

        class_name = uid.split("_")[0]
        base_logger = self.get_class_logger(class_name)
        return UidLoggerAdapter(base_logger, uid)

    def get_metrics_output_logger(self) -> logging.Logger:
        """
        Get a specialized logger for metrics output with simplified formatting.

        Metrics output does not require extra context like log level or UIDs, so
        we use a separate logger for this.

        Returns
        -------
        logging.Logger
            The metrics output logger with simplified formatting.
        """
        logger_name = "metrics.output"

        if logger_name not in self._loggers:
            logger = logging.getLogger(logger_name)
            logger.propagate = False

            metrics_formatter = logging.Formatter("%(message)s")

            # Create console handler for metrics
            metrics_console_handler = logging.StreamHandler()
            metrics_console_handler.setLevel(self._config.settings.LOG_LEVEL)
            metrics_console_handler.setFormatter(metrics_formatter)

            # Create file handler for metrics
            output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
            logs_dir = os.path.normpath(
                os.path.join(self._config.path.OUTPUT_FOLDER, "metrics_logs")
            )
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)

            metrics_log_file = os.path.join(logs_dir, f"{output_timestamp}_metrics.log")
            metrics_file_handler = logging.FileHandler(metrics_log_file)
            metrics_file_handler.setFormatter(metrics_formatter)
            metrics_file_handler.setLevel(self._config.settings.FILE_LOG_LEVEL)

            logger.addHandler(metrics_console_handler)
            logger.addHandler(metrics_file_handler)

            console_level = getattr(logging, self._config.settings.LOG_LEVEL)
            file_level = getattr(logging, self._config.settings.FILE_LOG_LEVEL)
            logger.setLevel(min(console_level, file_level))

            self._loggers[logger_name] = logger

        return self._loggers[logger_name]

    def _create_shared_handlers(self, config: Configuration) -> None:
        # Console handler
        self._shared_console_handler = logging.StreamHandler()
        self._shared_console_handler.setLevel(config.settings.LOG_LEVEL)
        self._shared_console_handler.setFormatter(self._formatter)

        # File handler setup
        output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        logs_dir = os.path.normpath(os.path.join(config.path.OUTPUT_FOLDER, "logs"))
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        log_file = os.path.join(logs_dir, f"{output_timestamp}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(self._formatter)
        file_handler.setLevel(config.settings.FILE_LOG_LEVEL)

        # Memory handler for buffered file writing
        self._shared_memory_handler = MemoryHandler(
            capacity=1000, flushLevel=logging.ERROR, target=file_handler
        )
        self._shared_memory_handler.setLevel(config.settings.FILE_LOG_LEVEL)
        atexit.register(self._shared_memory_handler.flush)

        # Override handlers for class overrides, set to lowest level to capture all logs
        self._override_console_handler = logging.StreamHandler()
        self._override_console_handler.setLevel(logging.DEBUG)
        self._override_console_handler.setFormatter(self._formatter)

        override_file_handler = logging.FileHandler(log_file)
        override_file_handler.setFormatter(self._formatter)
        override_file_handler.setLevel(logging.DEBUG)

        self._override_memory_handler = MemoryHandler(
            capacity=1000, flushLevel=logging.ERROR, target=override_file_handler
        )
        self._override_memory_handler.setLevel(logging.DEBUG)
        atexit.register(self._override_memory_handler.flush)

    def _create_formatter(self, config: Configuration) -> logging.Formatter:
        formatter = "[%(levelname)7s] [Time %(env_time)8s] [%(uid)25s]: %(message)s"
        if config.settings.LOG_TIMESTAMPS:
            formatter = "%(asctime)s " + formatter

        return logging.Formatter(formatter)
