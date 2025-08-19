"""Simulation module for setting up and running urban mobility simulations."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pandas as pd
from pandas import DataFrame

from simulation.context.simulation_context import SimulationContext
from simulation.metrics.metrics import Metrics
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
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

    def run_simulation(self, end_time: int | None = None) -> None:
        """
        Run a single simulation.

        Parameters
        ----------
        end_time : int or None
            End time for simulation. If None, uses configuration value.
        """
        if end_time is None:
            end_time = self.config.experiment_management.END_TIME

        self.demand_factory = self._create_demand_factory()
        self.demand_factory.reset()
        self.sim.env.process(self.demand_factory.generate_demand())

        self.logger.warning("Starting Simulation.")
        self.sim.env.run(until=end_time)
        self.logger.warning("Ending Simulation.")

        self._post_simulation_processing()

    def _load_supply_data(self) -> DataFrame:
        """Load vehicle supply probability data."""
        supply_path = os.path.normpath(self.config.path.PATH_VEHICLE_SUPPLY)
        return pd.read_csv(supply_path)

    def _create_demand_factory(self) -> DemandFactory:
        """Create demand factory for the simulation."""
        # TODO: Change this to support multiple operator types simultaneously
        # for now set mode to whatever operator is present, check in config
        if self.config.operators[0].OPERATOR_TYPE == RideHailingOperator:
            mode = "ride_hailing"
        elif self.config.operators[0].OPERATOR_TYPE == SharedMobilityOperator:
            mode = "shared_vehicle"
        else:
            mode = "public_transport"

        return DemandFactory(sim=self.sim, world=self.world, mode=mode)

    def _post_simulation_processing(self) -> None:
        """Handle post-simulation processing."""
        self.logger.info("Simulation completed")
