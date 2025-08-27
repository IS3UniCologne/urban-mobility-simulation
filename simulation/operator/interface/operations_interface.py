from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.helper.configuration.configuration import OperationsConfig
    from simulation.operator.operator import Operator


class OperationsInterface(ABC):
    @property
    @abstractmethod
    def operator(self) -> Operator:
        pass

    @property
    @abstractmethod
    def config(self) -> OperationsConfig:
        pass

    @abstractmethod
    def execute(self) -> None:
        pass
