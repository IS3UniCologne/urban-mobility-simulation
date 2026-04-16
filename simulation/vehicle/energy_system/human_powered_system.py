"""Human Power System Module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.vehicle.energy_system.base_energy_system import EnergySystem

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import VehicleConfig


class HumanPoweredSystem(EnergySystem):
    """
    Energy system for human-powered vehicles (Bikes, Walking).

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle_config : VehicleConfig
        The vehicle configuration.
    """

    def __init__(self, sim: SimulationContext, vehicle_config: VehicleConfig) -> None:
        super().__init__(sim, vehicle_config)
        if vehicle_config.ENERGY_CONSUMPTION_PER_KM > 0:
            self.logger.warning(
                "HumanPoweredSystem should have zero energy consumption."
            )
        self._current_energy = 100.0
        self._capacity = 100.0

    def consume_for_distance(self, distance: float) -> float:
        """
        Consume energy for a given distance. Only tracks emissions for human power.

        Parameters
        ----------
        distance : float
            Distance traveled in meters.

        Returns
        -------
        float
            Amount of energy consumed (always 0.0).
        """
        self._lifetime_emissions += self.calculate_emissions_for_distance(distance)
        self.logger.debug("Human powered travel for %s meters", distance)
        return 0.0

    def refill(self, amount: float, duration: float) -> Generator[Event, None, None]:
        """
        Refill energy. Does nothing for now :).

        Parameters
        ----------
        amount : float
            Amount to refill.
        duration : float
            Duration.

        Yields
        ------
        simpy.Event
            Simpy timeout event (0 duration).
        """
        yield self._env.timeout(0)
