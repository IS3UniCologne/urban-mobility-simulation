"""
Context management for simulation services and dependencies.

This package provides centralized access to core simulation services,
reducing the need to pass multiple dependencies throughout the codebase.
"""

from simulation.context.simulation_context import SimulationContext
from simulation.context.uid_manager import UidManager

__all__ = ["SimulationContext", "UidManager"]
