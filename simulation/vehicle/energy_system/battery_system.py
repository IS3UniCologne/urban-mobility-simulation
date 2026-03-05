"""Battery System Module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.vehicle.energy_system.base_energy_system import EnergySystem

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import VehicleConfig


class BatterySystem(EnergySystem):
    """
    Energy system for Battery Electric Vehicles.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle_config : VehicleConfig
        The vehicle configuration.
    """

    def __init__(self, sim: SimulationContext, vehicle_config: VehicleConfig) -> None:
        super().__init__(sim, vehicle_config)
        self._energy_consumption = vehicle_config.ENERGY_CONSUMPTION_PER_KM

    def consume_for_distance(self, distance: float) -> float:
        """
        Consume energy for a given distance.

        Parameters
        ----------
        distance : float
            Distance traveled in meters.

        Returns
        -------
        float
            Amount of energy consumed in kWh.
        """
        from simulation.helper.exceptions import EnergyDepletedError

        consumed = self.calculate_energy_required(distance)
        self._current_energy -= consumed
        if self._current_energy < 0:
            deficit = -self._current_energy
            self._current_energy = 0.0
            raise EnergyDepletedError(
                f"Battery depleted after traveling {distance}m. Deficit: {deficit:.2f} kWh."
            )

        self._lifetime_energy_consumed += consumed
        self._lifetime_emissions += self.calculate_emissions_for_distance(distance)

        self.logger.debug(
            "Consumed %s kWh energy for %s meters. SOC: %s kWh (%.2f%%)",
            consumed,
            distance,
            self.current_energy_absolute,
            self.current_energy_relative * 100,
        )
        return consumed

    def refill(self, amount: float, duration: float) -> Generator[Event, None, None]:
        """
        Charge the battery.

        Parameters
        ----------
        amount : float
            Amount of energy to add in kWh.
        duration : float
            Duration of the charging process in minutes.

        Yields
        ------
        simpy.Event
            Simpy timeout event for the charging duration.
        """
        if amount <= 0:
            amount = self._capacity - self._current_energy

        self.logger.debug("Charging %s energy over %s minutes", amount, duration)
        yield self._env.timeout(duration)
        self._current_energy += amount
        if self._current_energy > self._capacity:
            self._current_energy = self._capacity

        self.logger.debug("Charging complete. SOC: %s", self._current_energy)
