"""Abstract base class for service jobs dispatched to service workers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext


class ServiceJob(ABC, SimulationBase):
    """Dispatchable work executed by a ServiceWorker as part of operations ."""

    __slots__ = ("_env", "_finished", "_sim", "_start_time")

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._sim = sim
        self._env = sim.env
        self._start_time = self._env.now
        self._finished = self._env.event()

    @abstractmethod
    def execute(self) -> Generator[Event, None, None]:
        """Execute the job."""

    @property
    def finished(self) -> Event:
        """SimPy event that succeeds when the job completes."""
        return self._finished
