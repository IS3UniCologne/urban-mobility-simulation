"""Simulation module for setting up and running urban mobility simulations."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pandas as pd
import numpy as np
from pandas import DataFrame

from simulation.context.simulation_context import SimulationContext
from simulation.metrics.metrics import Metrics
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.world import World

if TYPE_CHECKING:
    from simulation.helper.configuration.configuration import Configuration


class Simulation:
    """Main simulation class that initializes and runs the simulation."""

    def __init__(self, config: Configuration) -> None:
        """
        Initialize the simulation with configuration.

        Parameters
        ----------
        config : Configuration
            Configuration object containing all simulation parameters.
        """
        self.config = config
        self.sim = SimulationContext(config)

        self.logger = self.sim.log_manager.get_class_logger(self.__class__.__name__)
        # TODO: Store config file and run information somewhere

        self.demand_factory: DemandFactory
        self.demand_profile: Any = None
        self.output_timestamp: str = ""

        self.supply_prob: DataFrame = self._load_supply_data()
        self.world = World(self.sim)
        self.metrics: Metrics = Metrics(simulation=self)

    def initialize_simulation(self) -> None:
        """Sets up the simulation environment up to time 0, ready to step."""
        self.demand_factory = self._create_demand_factory()
        self.sim.env.process(self.demand_factory.generate_demand())

        self.logger.info("Simulation initialized and ready.")

    def step_simulation(self, until_time: float) -> None:
        """Advances the simulation to a specific timestamp."""
        if self.sim.env.now < until_time:
            self.sim.env.run(until=until_time)

    def finalize_simulation(self) -> None:
        """Runs post-processing once the gym episode ends."""
        self.logger.info("Ending Simulation.")
        self._post_simulation_processing()

    def run_simulation(self, end_time: int | None = None) -> None:
        """Legacy method: Runs the whole thing standardly without Gym."""
        if end_time is None:
            end_time = self.config.experiment_management.END_TIME
        self.initialize_simulation()
        self.step_simulation(end_time)
        self.finalize_simulation()

    def _load_supply_data(self) -> DataFrame:
        """Load vehicle supply probability data."""
        supply_path = os.path.normpath(self.config.path.PATH_VEHICLE_SUPPLY)
        return pd.read_csv(supply_path)


    def _create_demand_factory(self) -> DemandFactory:
        """Create demand factory for the simulation."""
        return DemandFactory(sim=self.sim, world=self.world)

    def _post_simulation_processing(self) -> None:
        """Handle post-simulation processing."""
        self.logger.info("Simulation completed")
