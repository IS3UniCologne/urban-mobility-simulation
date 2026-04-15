"""Base class for vehicle tasks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event
    from simpy.core import Environment

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.vehicle.vehicle import Vehicle

from simulation.helper.enums import TaskState
from simulation.helper.exceptions import TaskAborted
from simulation.helper.simulation_base import SimulationBase

VehicleT = TypeVar("VehicleT", bound="Vehicle", covariant=True)


class VehicleTask(SimulationBase, ABC, Generic[VehicleT]):
    """Abstract base class for vehicle tasks.

    A task represents an interaction with a vehicle, such as
    relocating it, driving a user trip, or charging. One or more tasks are
    grouped into a ``VehicleSession``.

    ``execute()`` handles state management and logging.
    Subclasses implement their logic in ``_run()``.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : Vehicle
        The vehicle this task operates on.
    destination : GeodesicPosition or None
        Optional destination for the task.
    """

    __slots__ = ("_destination", "_env", "_sim", "_state", "_vehicle")

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: VehicleT,
        destination: GeodesicPosition | None = None,
    ) -> None:
        super().__init__(sim)
        self._sim: SimulationContext = sim
        self._env: Environment = sim.env
        self._destination: GeodesicPosition | None = destination
        self._vehicle: VehicleT = vehicle
        self._state: TaskState = TaskState.INITIALIZED

    @property
    def destination(self) -> GeodesicPosition | None:
        """Get the relocation destination."""
        return self._destination

    @property
    def state(self) -> TaskState:
        """Get the current state of the task."""
        return self._state

    @property
    def vehicle(self) -> VehicleT:
        """Get the vehicle this task operates on."""
        return self._vehicle

    def _abort(self) -> None:
        """Signal that the task should abort.

        Raises
        ------
        TaskAborted
            Always raised to unwind the generator stack.
        """
        raise TaskAborted

    def execute(self) -> Generator[Event, None, None]:
        """Execute the task with state management.

        Handles state transitions and logging.
        Subclasses implement their logic in ``_run()``.

        Yields
        ------
        Event
            SimPy events during task execution.
        """
        self._state = TaskState.EXECUTING

        self.logger.debug(
            "%s starting for vehicle %s.", self.__class__.__name__, self._vehicle.uid
        )

        try:
            yield from self._run()
            self._state = TaskState.FINISHED
            self.logger.debug(
                "%s finished for vehicle %s.",
                self.__class__.__name__,
                self._vehicle.uid,
            )
        except TaskAborted:
            self._state = TaskState.ABORTED
            self.logger.debug(
                "%s aborted for vehicle %s.", self.__class__.__name__, self._vehicle.uid
            )
        except Exception:
            self._state = TaskState.ABORTED
            self.logger.warning(
                "%s failed for vehicle %s.",
                self.__class__.__name__,
                self._vehicle.uid,
                exc_info=True,
            )
            raise

    @abstractmethod
    def _run(self) -> Generator[Event, None, None]:
        """Implement the task logic.

        Subclasses put their execution logic here.

        To abort, call ``self._abort()``.

        Yields
        ------
        Event
            SimPy events during task execution.
        """
        raise NotImplementedError

    @abstractmethod
    def get_predicted_energy_delta(
        self, prev_task_energy: float | None = None
    ) -> float:
        """Calculate predicted energy delta for this task.

        Positive values indicate energy gain, negative values indicate
        energy consumption.

        Parameters
        ----------
        prev_task_energy : float or None
            Predicted energy level from previous tasks in the session.
            When None, the task should use the vehicle's actual current
            energy.

        Returns
        -------
        float
            Predicted energy delta in kWh. Positive = gained,
            negative = consumed.
        """
        raise NotImplementedError

    @abstractmethod
    def get_predicted_duration(self, prev_task_energy: float | None = None) -> float:
        """Calculate predicted duration for this task.

        Parameters
        ----------
        prev_task_energy : float or None
            Predicted energy level from previous tasks in the session.
            When None, the task should use the vehicle's actual current
            energy.

        Returns
        -------
        float
            Predicted duration in minutes.
        """
        raise NotImplementedError
