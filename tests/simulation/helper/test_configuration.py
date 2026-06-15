"""Tests for the Configuration log-level environment override."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from simulation.helper.configuration.configuration import (
    LOG_LEVEL_ENV_VAR,
    Configuration,
)

if TYPE_CHECKING:
    import pytest

_FIXTURE_PROJECT = (
    Path(__file__).resolve().parents[2] / "configurations" / "balanced_rh"
)


def _read_config_log_level() -> str:
    with open(_FIXTURE_PROJECT / "config.toml", "rb") as f:
        return tomllib.load(f)["SETTINGS"]["LOG_LEVEL"]


_CONFIG_LOG_LEVEL = _read_config_log_level()


def test_no_env_uses_config_levels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LOG_LEVEL_ENV_VAR, raising=False)
    config = Configuration(_FIXTURE_PROJECT)
    assert config.settings.LOG_LEVEL == _CONFIG_LOG_LEVEL
    assert config.settings.FILE_LOG_LEVEL == _CONFIG_LOG_LEVEL


def test_env_overrides_both_levels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, "DEBUG")
    config = Configuration(_FIXTURE_PROJECT)
    assert config.settings.LOG_LEVEL == "DEBUG"
    assert config.settings.FILE_LOG_LEVEL == "DEBUG"


def test_env_override_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, "debug")
    config = Configuration(_FIXTURE_PROJECT)
    assert config.settings.LOG_LEVEL == "DEBUG"


def test_invalid_env_falls_back_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV_VAR, "LOUD")
    with caplog.at_level(logging.WARNING):
        config = Configuration(_FIXTURE_PROJECT)
    assert config.settings.LOG_LEVEL == _CONFIG_LOG_LEVEL
    assert any(LOG_LEVEL_ENV_VAR in record.message for record in caplog.records)
