"""VehicleTask for charging a vehicle at fleet base (charging only, no relocation)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.tasks.base.vehicle_task import VehicleTask

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.vehicle.shared_vehicle import SharedVehicle


class FleetBaseChargingTask(VehicleTask["SharedVehicle"]):
    """Charge to full capacity at fleet base.

    Lifecycle:
    1. Plug vehicle
    2. Charge vehicle to full capacity
    3. Unplug vehicle from charging station

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : SharedVehicle
        The vehicle to charge (already at fleet base).
    charging_power : float
        Power of the charging station in kW.
    linearization_factor : int
        Number of vehicles being charged in parallel. Duration is divided
        by this factor to simulate parallel charging.
    """

    __slots__ = ("_charging_power", "_linearization_factor")

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: SharedVehicle,
        charging_power: float,
        linearization_factor: int = 1,
    ) -> None:
        super().__init__(sim, vehicle)
        self._charging_power = charging_power
        self._linearization_factor = linearization_factor

    def _compute_charging_duration(self, current_energy: float | None = None) -> float:
        if current_energy is None:
            current_energy = self._vehicle.energy_system.current_energy_absolute
        energy_deficit = self._vehicle.energy_system.capacity - current_energy
        if energy_deficit <= 0 or self._charging_power <= 0:
            return 0.0
        return (energy_deficit / self._charging_power) * 60 / self._linearization_factor

    def _run(self) -> Generator[Event, None, None]:
        duration = self._compute_charging_duration()
        if duration <= 0:
            self.logger.debug(
                "Skipping charging for vehicle %s (already full).", self._vehicle.uid
            )
            return

        self._vehicle.plug_to_charging_station()

        yield self._env.process(self._vehicle.charge(duration))

        self._vehicle.unplug_from_charging_station()

    def get_predicted_energy_delta(self, current_energy: float | None = None) -> float:
        """Calculate predicted energy gain from charging.

        Parameters
        ----------
        current_energy : float or None
            Running energy level from previous tasks. When None, uses
            vehicle's actual current energy.

        Returns
        -------
        float
            Net energy delta in kWh (positive = energy gain).
        """
        if current_energy is None:
            current_energy = self._vehicle.energy_system.current_energy_absolute

        charging_energy_gain = self._vehicle.energy_system.capacity - current_energy
        return charging_energy_gain

    def get_predicted_duration(self, current_energy: float | None = None) -> float:
        """Calculate predicted duration for charging.

        Parameters
        ----------
        current_energy : float or None
            Running energy level from previous tasks. When None, uses
            vehicle's actual current energy.

        Returns
        -------
        float
            Predicted duration in minutes (charging only).
        """
        return self._compute_charging_duration(current_energy)
