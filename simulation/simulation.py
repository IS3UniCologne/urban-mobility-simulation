"""Simulation module for setting up and running urban mobility simulations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
        self.sim.env.process(self.demand_factory.generate_demand())

        self.logger.info("Starting Simulation.")
        self.sim.env.run(until=end_time)
        self.sim.mark_ended()
        self.logger.info("Ending Simulation.")

        self._post_simulation_processing()

    def _create_demand_factory(self) -> DemandFactory:
        """Create demand factory for the simulation."""
        return DemandFactory(sim=self.sim, world=self.world)

    def _post_simulation_processing(self) -> None:
        """Handle post-simulation processing."""
        self.logger.info("Simulation completed")

    def step_simulation(self, until_time: float) -> None:
        """Advances the simulation to a specific timestamp."""
        if self.sim.env.now < until_time:
            self.sim.env.run(until=until_time)