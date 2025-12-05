"""Energy System Package.

Contains various energy system implementations for vehicles. These handle
energy consumption, state of charge, emissions and related functionalities.
"""

from simulation.vehicle.energy_system.base_energy_system import EnergySystem
from simulation.vehicle.energy_system.battery_system import BatterySystem
from simulation.vehicle.energy_system.factory import create_energy_system
from simulation.vehicle.energy_system.human_powered_system import HumanPoweredSystem
from simulation.vehicle.energy_system.internal_combustion_system import (
    InternalCombustionSystem,
)

__all__ = [
    "BatterySystem",
    "EnergySystem",
    "HumanPoweredSystem",
    "InternalCombustionSystem",
    "create_energy_system",
]
