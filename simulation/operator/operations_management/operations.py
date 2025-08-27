from __future__ import annotations  # noqa: D100

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase
from simulation.operator.interface.operations_interface import OperationsInterface

if TYPE_CHECKING:
    import pandas as pd

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import OperationsConfig
    from simulation.operator.operator import Operator
    from simulation.world.world import World


@dataclass(frozen=True, slots=True)
class OperationsDependencies:
    """Construction dependencies for operations.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    operator : Operator
        The owning operator instance.
    world : World
        The simulation world.
    operations_config : OperationsConfig
        The operations-related configuration section.
    distance_matrix : pandas.DataFrame or None
        Region-to-region distance matrix.
    """

    sim: SimulationContext
    operator: Operator
    world: World  # TODO: this should go
    operations_config: OperationsConfig
    distance_matrix: pd.DataFrame | None = None


class Operations(SimulationBase, OperationsInterface):  # noqa: D101
    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps.sim)
        # TODO: operations subclasses currently share a lot of logic. Move stuff here where possible.
        self._sim = deps.sim
        self._env = deps.sim.env
        self._operator = deps.operator
        self._world = deps.world
        self._config = deps.operations_config
        self._distance_matrix = deps.distance_matrix

    @classmethod
    def from_deps(cls, deps: OperationsDependencies) -> Operations:  # noqa: D102
        operations_type = deps.operations_config.OPERATIONS_TYPE
        return operations_type(deps)

    @property
    def operator(self) -> Operator:  # noqa: D102
        return self._operator

    @property
    def config(self) -> OperationsConfig:  # noqa: D102
        return self._config
