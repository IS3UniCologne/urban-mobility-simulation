from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.context.simulation_context import SimulationContext
from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.operator.operator import Operator


class OperationsInterface(ABC, SimulationBase):
    __slots__ = ("_env", "_operator_reference")

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._env = sim.env
        self._operator_reference = None

    @property
    def operator(self) -> "Operator":
        """Get the operator with guaranteed type safety."""
        if self._operator_reference is None:
            raise RuntimeError(
                "Operator reference not set. Call register_operator_reference first."
            )
        # Use cast to tell the type checker this is definitely an Operator
        return self._operator_reference

    @abstractmethod
    def execute(self) -> None:
        pass
