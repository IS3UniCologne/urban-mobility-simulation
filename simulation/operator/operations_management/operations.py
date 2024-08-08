from abc import ABC, abstractmethod

from simpy import Environment


class OperationsInterface(ABC):
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

    @abstractmethod
    def execute(self) -> None:
        pass
