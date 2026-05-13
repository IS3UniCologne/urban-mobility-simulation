from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.helper.configuration.configuration import OperationsConfig
    from simulation.operator.operator import Operator


class OperationsInterface(ABC):  # noqa: D101
    @property
    @abstractmethod
    def operator(self) -> Operator:  # noqa: D102
        pass

    @property
    @abstractmethod
    def config(self) -> OperationsConfig:  # noqa: D102
        pass

    @abstractmethod
    def execute(self) -> Generator[Event, None, None]:  # noqa: D102
        pass
