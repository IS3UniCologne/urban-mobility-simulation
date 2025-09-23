from __future__ import annotations  # noqa: D100

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    AllocationEngineInterface,
)

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import AllocationEngineConfig


@dataclass(frozen=True, slots=True)
class AllocationEngineDependencies:
    """Dependencies for the Vehicle Allocation Engine."""

    sim: SimulationContext
    config: AllocationEngineConfig


class AllocationEngine(SimulationBase, AllocationEngineInterface):  # noqa: D101
    def __init__(self, deps: AllocationEngineDependencies) -> None:
        super().__init__(deps.sim)

    @staticmethod
    def from_deps(deps: AllocationEngineDependencies) -> AllocationEngine:  # noqa: D102
        allocation_engine_type = deps.config.VEHICLE_ALLOCATION_ENGINE_TYPE
        return allocation_engine_type(deps)
