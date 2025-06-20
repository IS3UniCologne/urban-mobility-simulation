"""
LogManager for centralized logging setup.

This class encapsulates all logging configuration, including formatters, handlers, log levels, and filters.

TODO: Since logging is a global resource, logging config should probably be moved to its own file.
"""

from __future__ import annotations

import atexit
import logging
import os
from datetime import datetime
from logging.handlers import MemoryHandler
from typing import TYPE_CHECKING, ClassVar

from simulation.helper.logging.extra_default_filter import UidInjector
from simulation.helper.logging.simulation_context_filter import EnvTimeInjector

if TYPE_CHECKING:
    import simpy

    from simulation.helper.configuration.configuration import Configuration
    from simulation.helper.logging.uid_logger_adapter import UidLoggerAdapter


class LogManager:
    """
    Centralized logging manager.

    Methods
    -------
    setup_logging(config, env=None):
        Set up logging with the given configuration and optional SimPy environment.
    get_class_logger(cls_name):
        Get or create a logger for a specific class.
    """

    _loggers: ClassVar[dict[str, logging.Logger]] = {}
    _config: ClassVar[Configuration]
    _class_overrides: ClassVar[dict[str, str]]
    _formatter: ClassVar[logging.Formatter]
    _env_time_injector: ClassVar[EnvTimeInjector]
    _uid_injector: ClassVar[UidInjector]
    _shared_console_handler: ClassVar[logging.Handler]
    _shared_memory_handler: ClassVar[MemoryHandler]
    _override_console_handler: ClassVar[logging.Handler]
    _override_memory_handler: ClassVar[MemoryHandler]
    _is_initialized: ClassVar[bool] = False

    @classmethod
    def setup_logging(cls, config: Configuration, env: simpy.Environment) -> None:
        """
        Set up logging for the simulation.

        Loads config into class variables, creates shared handlers, formatter, and filters.

        Parameters
        ----------
        config : Configuration
            The configuration object containing logging settings and paths.
        env : simpy.Environment or None
            The simulation environment, used for env_time in logs.
        """
        if cls._is_initialized:
            raise RuntimeError(
                "LogManager has already been initialized. Call setup_logging only once."
            )

        cls._config = config
        cls._class_overrides = config.settings.LOG_CLASS_OVERRIDES or {}
        cls._formatter = cls._create_formatter(config)

        cls._create_shared_handlers(config)

        logging.getLogger().handlers.clear()
        logger = logging.getLogger()

        console_level = getattr(logging, config.settings.LOG_LEVEL)
        file_level = getattr(logging, config.settings.FILE_LOG_LEVEL)
        logger.setLevel(min(console_level, file_level))

        logging.getLogger("fiona").setLevel(logging.WARNING)
        logging.getLogger("docplex.util.environment.logger").setLevel(logging.WARNING)

        logger.addHandler(cls._shared_console_handler)
        logger.addHandler(cls._shared_memory_handler)

        uid_filter = UidInjector(filter_name="add_default_value")
        logger.addFilter(uid_filter)
        env_time_filter = EnvTimeInjector(filter_name="add_env", env=env)
        logger.addFilter(env_time_filter)

        cls._uid_injector = uid_filter
        cls._env_time_injector = env_time_filter

        cls._is_initialized = True

    @classmethod
    def get_class_logger(cls, cls_name: str) -> logging.Logger:
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
        if cls_name not in cls._loggers:
            if not cls._is_initialized:
                raise RuntimeError(
                    "LogManager has not been initialized with setup_logging. "
                    "Call setup_logging before using get_class_logger."
                )

            logger = logging.getLogger(cls_name)
            logger.propagate = False

            if cls_name in cls._class_overrides:
                logger.addHandler(cls._override_console_handler)
                logger.addHandler(cls._override_memory_handler)

                override_level_str = cls._class_overrides[cls_name]
                override_level = getattr(logging, override_level_str.upper())
                logger.setLevel(override_level)
            else:
                logger.addHandler(cls._shared_console_handler)
                logger.addHandler(cls._shared_memory_handler)

                console_level = getattr(logging, cls._config.settings.LOG_LEVEL)
                file_level = getattr(logging, cls._config.settings.FILE_LOG_LEVEL)
                logger.setLevel(min(console_level, file_level))

            logger.addFilter(cls._uid_injector)
            logger.addFilter(cls._env_time_injector)

            cls._loggers[cls_name] = logger

        return cls._loggers[cls_name]

    @classmethod
    def get_uid_logger(cls, uid: str) -> UidLoggerAdapter:
        """
        Get a logger adapter that automatically includes UID in all log records.

        Parameters
        ----------
        uid : str
            The unique identifier to include in all log records.

        Returns
        -------
        UidLoggerAdapter
            The logger adapter instance that automatically adds UID context.
        """
        # Import here to avoid circular dependency
        from simulation.helper.logging.uid_logger_adapter import UidLoggerAdapter

        class_name = uid.split("_")[0]
        base_logger = cls.get_class_logger(class_name)
        return UidLoggerAdapter(base_logger, uid)

    @classmethod
    def _create_shared_handlers(cls, config: Configuration) -> None:
        cls._shared_console_handler = logging.StreamHandler()
        cls._shared_console_handler.setLevel(config.settings.LOG_LEVEL)
        cls._shared_console_handler.setFormatter(cls._formatter)

        output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        logs_dir = os.path.normpath(os.path.join(config.path.OUTPUT_FOLDER, "logs"))
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        log_file = os.path.join(logs_dir, f"{output_timestamp}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(cls._formatter)
        file_handler.setLevel(config.settings.FILE_LOG_LEVEL)

        cls._shared_memory_handler = MemoryHandler(
            capacity=1000, flushLevel=logging.ERROR, target=file_handler
        )
        cls._shared_memory_handler.setLevel(config.settings.FILE_LOG_LEVEL)
        atexit.register(cls._shared_memory_handler.flush)

        cls._override_console_handler = logging.StreamHandler()
        cls._override_console_handler.setLevel(logging.DEBUG)
        cls._override_console_handler.setFormatter(cls._formatter)

        output_timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        logs_dir = os.path.normpath(os.path.join(config.path.OUTPUT_FOLDER, "logs"))
        log_file = os.path.join(logs_dir, f"{output_timestamp}.log")
        override_file_handler = logging.FileHandler(log_file)
        override_file_handler.setFormatter(cls._formatter)
        override_file_handler.setLevel(logging.DEBUG)

        cls._override_memory_handler = MemoryHandler(
            capacity=1000, flushLevel=logging.ERROR, target=override_file_handler
        )
        cls._override_memory_handler.setLevel(logging.DEBUG)
        atexit.register(cls._override_memory_handler.flush)

    @staticmethod
    def _create_formatter(config: Configuration) -> logging.Formatter:
        formatter = "[%(levelname)s] [Time %(env_time)10s] [%(uid)30s]: %(message)s"
        if config.settings.LOG_TIMESTAMPS:
            formatter = "%(asctime)s " + formatter

        return logging.Formatter(formatter)
