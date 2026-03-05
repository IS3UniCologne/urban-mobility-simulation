"""Base Energy System Module."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import VehicleConfig


class EnergySystem(SimulationBase, ABC):
    """
    Abstract base class for vehicle energy systems.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle_config : VehicleConfig
        The vehicle configuration.
    """

    def __init__(self, sim: SimulationContext, vehicle_config: VehicleConfig) -> None:
        super().__init__(sim)
        self._env = sim.env
        self._energy_consumption = vehicle_config.ENERGY_CONSUMPTION_PER_KM
        self._capacity = vehicle_config.ENERGY_CAPACITY

        self._current_energy = self._capacity * (
            vehicle_config.INITIAL_CHARGE_RATIO or 1.0
        )

        self._lifetime_energy_consumed = 0.0
        self._lifetime_emissions = 0.0
        self._co2_per_km = vehicle_config.KG_CO2_PER_KM or 0.0

        self._default_buffer = (
            vehicle_config.ENERGY_RESERVE_RATIO or 0.0
        ) * self._capacity

        self._predicted_energy: float | None = None

        self.logger.debug(
            "Initialized EnergySystem with capacity %s and consumption %s",
            self._capacity,
            self._energy_consumption,
        )

    @property
    def current_energy_absolute(self) -> float:
        """Current energy level (kWh or Liters)."""
        return self._current_energy

    @property
    def lifetime_energy_consumed(self) -> float:
        """Lifetime energy consumed (kWh or Liters)."""
        return self._lifetime_energy_consumed

    @property
    def lifetime_emissions(self) -> float:
        """Lifetime CO2 emissions (kg)."""
        return self._lifetime_emissions

    @property
    def capacity(self) -> float:
        """Maximum energy capacity."""
        return self._capacity

    @property
    def energy_consumption_per_km(self) -> float:
        """Energy consumption per kilometer."""
        return self._energy_consumption

    @property
    def current_energy_relative(self) -> float:
        """Relative energy level (0.0 to 1.0)."""
        if self._capacity == 0:
            return 0.0
        return self._current_energy / self._capacity

    @property
    def predicted_energy(self) -> float:
        """Predicted absolute energy level after completing current session.

        Falls back to current energy if no prediction is set.

        Returns
        -------
        float
            Predicted energy level in absolute units.
        """
        return (
            self._predicted_energy
            if self._predicted_energy is not None
            else self._current_energy
        )

    @predicted_energy.setter
    def predicted_energy(self, value: float | None) -> None:
        """Set predicted absolute energy level after completing current session.

        Parameters
        ----------
        value : float or None
            Predicted energy level in absolute units.
        """
        self._predicted_energy = value

    @property
    def predicted_energy_relative(self) -> float:
        """Predicted relative energy level (0.0 to 1.0) after completing current session.

        Falls back to current energy if no prediction is set.

        Returns
        -------
        float
            Predicted energy level as ratio of capacity.
        """
        if self._predicted_energy is None:
            return self.current_energy_relative
        if self._capacity == 0:
            return 0.0
        return self._predicted_energy / self._capacity

    def calculate_energy_required(self, distance: float) -> float:
        """
        Calculate the energy required for a given distance.

        Parameters
        ----------
        distance : float
            Distance in meters.

        Returns
        -------
        float
            Energy required.
        """
        return self._energy_consumption * distance / 1000

    def calculate_emissions_for_distance(self, distance: float) -> float:
        """
        Calculate the CO2 emissions for a given distance.

        Parameters
        ----------
        distance : float
            Distance in meters.

        Returns
        -------
        float
            CO2 emissions in kg.
        """
        return (distance / 1000) * self._co2_per_km

    @abstractmethod
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
            Amount of energy consumed.
        """

    def has_enough_energy(self, distance: float, *, use_buffer: bool = True) -> bool:
        """Check if predicted energy covers distance.

        Uses predicted energy after current session if available,
        falls back to current energy otherwise.

        Parameters
        ----------
        distance : float
            Distance to travel in meters.
        use_buffer : bool
            If True (default), hold back the configured energy reserve buffer.
            Set to False when the vehicle must use all remaining energy,
            e.g. driving to a charging station.

        Returns
        -------
        bool
            True if enough energy is available.
        """
        required = self.calculate_energy_required(distance)
        buffer = self._default_buffer if use_buffer else 0.0
        return self.predicted_energy >= (required + buffer)

    def clear_predicted_energy(self) -> None:
        """Clear the predicted energy level."""
        self._predicted_energy = None

    @abstractmethod
    def refill(self, amount: float, duration: float) -> Generator[Event, None, None]:
        """
        Refill energy (charge or refuel).

        Parameters
        ----------
        amount : float
            Amount of energy to add.
        duration : float
            Duration of the refill process.

        Yields
        ------
        simpy.Event
            Timeout event for the duration.
        """
