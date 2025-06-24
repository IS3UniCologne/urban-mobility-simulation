"""Simulation context for managing core simulation components."""

from __future__ import annotations

from typing import TYPE_CHECKING

import simpy

from simulation.context.uid_manager import UidManager
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.logging.log_manager import LogManager
from simulation.helper.random.random_manager import RandomManager

if TYPE_CHECKING:
    from simulation.helper.configuration.configuration import Configuration


class SimulationContext:
    """
    Central context holding all core simulation components.

    This class provides a single point of access to commonly used
    simulation components, reducing the need to pass multiple dependencies
    around the codebase.
    Using an instance based context with dependency injection allows for
    easier testing and proper isolation of multiple simulations.
    """

    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._env: simpy.Environment = simpy.Environment(
            initial_time=self.config.experiment_management.START_TIME
        )
        self._log_manager = LogManager(config=self.config, env=self.env)
        self._uid_manager = UidManager()
        self._random_manager = RandomManager(self)
        self._geo_env = GeodesicEnvironment(sim=self)

    @property
    def env(self) -> simpy.Environment:
        """Get the simulation environment."""
        return self._env

    @property
    def config(self) -> Configuration:
        """Get the configuration."""
        return self._config

    @property
    def random_manager(self) -> RandomManager:
        """Get the random manager."""
        return self._random_manager

    @property
    def geo_env(self) -> GeodesicEnvironment:
        """Get the geodesic environment."""
        return self._geo_env

    @property
    def log_manager(self) -> LogManager:
        """Get the log manager."""
        return self._log_manager

    @property
    def uid_manager(self) -> UidManager:
        """Get the UID manager."""
        return self._uid_manager

    @property
    def time(self) -> float:
        """Get current simulation time."""
        return self._env.now
