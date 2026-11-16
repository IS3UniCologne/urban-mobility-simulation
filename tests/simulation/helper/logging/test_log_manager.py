import logging
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from simulation.helper.logging.log_manager import LogManager

"""Unit tests for LogManager class."""


@pytest.mark.unit
class TestLogManager:
    """Unit tests for LogManager functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: Path) -> None:
        """Set up test environment before each test method."""

        # Create mock configuration
        self.config = Mock()
        self.config.settings = Mock()
        self.config.settings.LOG_LEVEL = "WARNING"
        self.config.settings.FILE_LOG_LEVEL = "INFO"
        self.config.settings.LOG_TIMESTAMPS = True
        self.config.settings.LOG_CLASS_OVERRIDES = {"TestClass": "DEBUG"}
        self.config.path = Mock()
        self.config.path.OUTPUT_FOLDER = str(tmp_path)

        # Create mock SimPy environment
        self.env = Mock()

    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    @patch("simulation.helper.logging.log_manager.datetime")
    def test_should_initialize_logging_successfully_when_valid_config_provided(
        self, mock_datetime: Mock, mock_file_handler: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that LogManager initializes logging correctly with valid configuration."""
        # Arrange
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.strftime = datetime.strftime
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance

        # Act
        log_manager = LogManager(self.config, self.env)

        # Assert
        assert log_manager._config is self.config
        assert log_manager._class_overrides == {"TestClass": "DEBUG"}
        mock_makedirs.assert_called_once()
        mock_file_handler.assert_called()

    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    def test_should_create_class_logger_with_shared_handlers_when_no_override(
        self, mock_file_handler: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that get_class_logger creates logger with shared handlers for regular classes."""
        # Arrange
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance
        log_manager = LogManager(self.config, self.env)

        # Act
        logger = log_manager.get_class_logger("RegularClass")

        # Assert
        assert isinstance(logger, logging.Logger)
        assert logger.name == "RegularClass"
        assert logger.propagate is False
        assert len(logger.handlers) == 2
        assert logger.level == logging.INFO  # min(INFO, WARNING)

    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    def test_should_create_class_logger_with_override_handlers_when_override_exists(
        self, mock_file_handler: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that get_class_logger creates logger with override handlers for override classes."""
        # Arrange
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance
        log_manager = LogManager(self.config, self.env)

        # Act
        logger = log_manager.get_class_logger("TestClass")

        # Assert
        assert isinstance(logger, logging.Logger)
        assert logger.name == "TestClass"
        assert logger.propagate is False
        assert len(logger.handlers) == 2
        assert logger.level == logging.DEBUG

    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    def test_should_return_same_logger_instance_when_called_multiple_times(
        self, mock_file_handler: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that get_class_logger returns the same instance for multiple calls with same class name."""
        # Arrange
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance
        log_manager = LogManager(self.config, self.env)

        # Act
        logger1 = log_manager.get_class_logger("TestClass")
        logger2 = log_manager.get_class_logger("TestClass")

        # Assert
        assert logger1 is logger2

    def test_should_create_formatter_with_timestamps_when_enabled(self) -> None:
        """Test that _create_formatter includes timestamps when LOG_TIMESTAMPS is True."""
        # Arrange
        self.config.settings.LOG_TIMESTAMPS = True
        log_manager = LogManager(config=self.config, env=self.env)

        # Act
        formatter = log_manager._create_formatter(self.config)

        # Assert
        assert isinstance(formatter, logging.Formatter)
        assert "%(asctime)s" in formatter._fmt

    def test_should_create_formatter_without_timestamps_when_disabled(self) -> None:
        """Test that _create_formatter excludes timestamps when LOG_TIMESTAMPS is False."""
        # Arrange
        self.config.settings.LOG_TIMESTAMPS = False
        log_manager = LogManager(config=self.config, env=self.env)

        # Act
        formatter = log_manager._create_formatter(self.config)

        # Assert
        assert isinstance(formatter, logging.Formatter)
        assert "%(asctime)s" not in formatter._fmt

    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    @patch("simulation.helper.logging.log_manager.datetime")
    def test_should_create_log_directory(
        self, mock_datetime: Mock, mock_file_handler: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that LogManager creates its log directory, tolerating an existing one."""
        # Arrange
        mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.strftime = datetime.strftime
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance

        # Act
        LogManager(self.config, self.env)

        # Assert
        expected_logs_dir = os.path.normpath(
            os.path.join(self.config.path.OUTPUT_FOLDER, "logs")
        )
        mock_makedirs.assert_called_once_with(expected_logs_dir, exist_ok=True)

    @patch("simulation.helper.logging.log_manager.atexit.register")
    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    def test_should_register_memory_handler_flush_on_exit(
        self, mock_file_handler: Mock, mock_makedirs: Mock, mock_atexit_register: Mock
    ) -> None:
        """Test that memory handler flush is registered with atexit."""
        # Arrange
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance

        # Act
        LogManager(self.config, self.env)

        # Assert
        assert mock_atexit_register.call_count == 2  # One for shared, one for override

    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    def test_should_return_uid_logger_adapter_when_get_uid_logger_called(
        self, mock_file_handler: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that get_uid_logger returns UidLoggerAdapter with correct configuration."""
        # Arrange
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance
        log_manager = LogManager(self.config, self.env)

        with patch(
            "simulation.helper.logging.uid_logger_adapter.UidLoggerAdapter"
        ) as mock_adapter_class:
            mock_adapter_instance = Mock()
            mock_adapter_class.return_value = mock_adapter_instance

            # Act
            result = log_manager.get_uid_logger("TestClass_123")

            # Assert
            assert result is mock_adapter_instance
            mock_adapter_class.assert_called_once()

            # Verify the adapter was created with correct base logger and UID
            call_args = mock_adapter_class.call_args
            base_logger = call_args[0][0]
            uid = call_args[0][1]

            assert base_logger.name == "TestClass"
            assert uid == "TestClass_123"

    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    def test_should_extract_class_name_from_uid_correctly(
        self, mock_file_handler: Mock, mock_makedirs: Mock
    ) -> None:
        """Test that get_uid_logger correctly extracts class name from UID."""
        # Arrange
        mock_file_handler_instance = Mock()
        mock_file_handler.return_value = mock_file_handler_instance
        log_manager = LogManager(self.config, self.env)

        with patch(
            "simulation.helper.logging.uid_logger_adapter.UidLoggerAdapter"
        ) as mock_adapter_class:
            mock_adapter_instance = Mock()
            mock_adapter_class.return_value = mock_adapter_instance

            # Act
            log_manager.get_uid_logger("ComplexClassName_456_extra")

            # Assert
            call_args = mock_adapter_class.call_args
            base_logger = call_args[0][0]

            assert base_logger.name == "ComplexClassName"

    def test_should_handle_none_class_overrides_gracefully(self) -> None:
        """Test that LogManager handles None class overrides without error."""
        # Arrange
        self.config.settings.LOG_CLASS_OVERRIDES = None

        with (
            patch("simulation.helper.logging.log_manager.os.makedirs"),
            patch("simulation.helper.logging.log_manager.logging.FileHandler"),
        ):
            # Act & Assert (should not raise exception)
            log_manager = LogManager(self.config, self.env)
            assert log_manager._class_overrides == {}

    @pytest.mark.parametrize(
        "log_level,file_log_level,expected_min_level",
        [
            ("INFO", "DEBUG", logging.DEBUG),
            ("DEBUG", "INFO", logging.DEBUG),
            ("WARNING", "ERROR", logging.WARNING),
            ("ERROR", "WARNING", logging.WARNING),
        ],
    )
    @patch("simulation.helper.logging.log_manager.os.makedirs")
    @patch("simulation.helper.logging.log_manager.logging.FileHandler")
    def test_initialization_sets_correct_root_level(
        self,
        mock_file_handler: Mock,
        mock_makedirs: Mock,
        log_level: str,
        file_log_level: str,
        expected_min_level: int,
    ) -> None:
        """Test that initialization sets root logger to minimum of console and file levels.

        Parameters
        ----------
        log_level : str
            Console log level setting.
        file_log_level : str
            File log level setting.
        expected_min_level : int
            Expected minimum log level that should be set.
        """
        # Arrange
        self.config.settings.LOG_LEVEL = log_level
        self.config.settings.FILE_LOG_LEVEL = file_log_level

        # Act
        LogManager(self.config, self.env)

        # Assert - Check the actual state instead of mock calls
        root_logger = logging.getLogger()
        assert root_logger.level == expected_min_level


@pytest.mark.unit
class TestLogManagerClose:
    """Unit tests for releasing a LogManager's handlers."""

    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: "os.PathLike[str]") -> None:
        """Point a real configuration stub at a temporary output folder."""
        self.config = Mock()
        self.config.settings = Mock()
        self.config.settings.LOG_LEVEL = "WARNING"
        self.config.settings.FILE_LOG_LEVEL = "INFO"
        self.config.settings.LOG_TIMESTAMPS = False
        self.config.settings.LOG_CLASS_OVERRIDES = {"Overridden": "DEBUG"}
        self.config.path = Mock()
        self.config.path.OUTPUT_FOLDER = str(tmp_path)
        self.env = Mock()

    def test_close_detaches_and_closes_every_handler(self) -> None:
        """After close no logger holds the manager's handlers and its files are shut."""
        manager = LogManager(self.config, self.env)
        class_logger = manager.get_class_logger("Plain")
        override_logger = manager.get_class_logger("Overridden")
        system_logger = manager.get_system_logger("boot")
        metrics_logger = manager.get_metrics_output_logger()
        metrics_file_handler = next(
            h for h in metrics_logger.handlers if isinstance(h, logging.FileHandler)
        )

        manager.close()

        for logger in (class_logger, override_logger, system_logger, metrics_logger):
            assert logger.handlers == []
        root = logging.getLogger()
        assert manager._shared_console_handler not in root.handlers
        assert manager._shared_memory_handler not in root.handlers
        assert manager._shared_file_handler.stream is None
        assert manager._override_file_handler.stream is None
        assert metrics_file_handler.stream is None

    @patch("simulation.helper.logging.log_manager.atexit.unregister")
    def test_close_unregisters_its_exit_hooks(self, mock_unregister: Mock) -> None:
        """Both exit flushes are unregistered, and a second close is harmless."""
        manager = LogManager(self.config, self.env)

        manager.close()
        manager.close()

        mock_unregister.assert_any_call(manager._shared_memory_handler.flush)
        mock_unregister.assert_any_call(manager._override_memory_handler.flush)

    def test_close_leaves_a_newer_manager_untouched(self) -> None:
        """Closing an older manager keeps a newer one's handlers on the shared loggers."""
        older = LogManager(self.config, self.env)
        older.get_class_logger("Plain")
        older.get_system_logger("boot")
        older.get_metrics_output_logger()
        newer = LogManager(self.config, self.env)
        plain = newer.get_class_logger("Plain")
        metrics_logger = newer.get_metrics_output_logger()
        metrics_file_handler = next(
            h for h in metrics_logger.handlers if isinstance(h, logging.FileHandler)
        )

        older.close()

        assert plain.handlers == [
            newer._shared_console_handler,
            newer._shared_memory_handler,
        ]
        assert newer._shared_file_handler.stream is not None
        assert metrics_file_handler.stream is not None
        newer.close()
