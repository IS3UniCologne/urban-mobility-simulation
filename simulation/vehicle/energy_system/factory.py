"""Energy System Factory Module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import PropulsionType
from simulation.vehicle.energy_system.battery_system import BatterySystem
from simulation.vehicle.energy_system.human_power_system import HumanPoweredSystem
from simulation.vehicle.energy_system.internal_combustion_system import (
    InternalCombustionSystem,
)

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.vehicle.energy_system.base_energy_system import EnergySystem


def create_energy_system(
    sim: SimulationContext, vehicle_config: VehicleConfig
) -> EnergySystem:
    """
    Create the appropriate energy system based on configuration.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle_config : VehicleConfig
        Vehicle configuration.

    Returns
    -------
    EnergySystem
        The created energy system instance.
    """
    if vehicle_config.PROPULSION_TYPE == PropulsionType.BATTERY_ELECTRIC:
        return BatterySystem(sim, vehicle_config)
    elif vehicle_config.PROPULSION_TYPE == PropulsionType.INTERNAL_COMBUSTION:
        return InternalCombustionSystem(sim, vehicle_config)
    elif vehicle_config.PROPULSION_TYPE == PropulsionType.HUMAN_POWERED:
        return HumanPoweredSystem(sim, vehicle_config)
    else:
        raise NotImplementedError(
            f"Energy system for propulsion type "
            f"{vehicle_config.PROPULSION_TYPE} is not implemented."
        )
