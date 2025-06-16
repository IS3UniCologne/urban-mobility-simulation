from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simpy import Environment

if TYPE_CHECKING:
    from simulation.operator.operator import Operator


class OperationsInterface(ABC):
    __slots__ = ("_env", "_operator_reference")

    def __init__(self, env: Environment) -> None:
        self._env = env
        self._operator_reference = None

    def register_operator_reference(self, operator_reference: "Operator") -> None:
        """
        Because we defer the registration of the operator back reference, we need to check, that it was not registered (which might happen if you unintentionally use the same strategy object for multiple operators. It is okay to use the same strategy for multiple operators, but then you need to initialize as many strategy objects.)

        :param operator_reference: back-reference to the operator that executes this strategy
        :return:
        """
        try:
            assert self._operator_reference is None
        except AssertionError as e:
            raise ValueError(
                "Attention: Another operator back-reference is already set! Do you need to initialize multiple strategies?"
            ) from e
        self._operator_reference = operator_reference

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
