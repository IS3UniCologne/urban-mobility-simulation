"""VehicleSession represents one actor's complete interaction with a vehicle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.enums import TaskState
from simulation.helper.exceptions import ReservationCanceledError
from simulation.vehicle.interfaces.reservable_interface import ReservableInterface

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.tasks.base.vehicle_task import VehicleTask
    from simulation.vehicle.reservation import Reservation
    from simulation.vehicle.vehicle import Vehicle

from simulation.helper.simulation_base import SimulationBase


class VehicleSession(SimulationBase):
    """One actor's complete interaction with a vehicle from start to finish.

    Automatically manages vehicl lock acquisition and release.
    Calculates predicted energy and duration for the whole session.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : Vehicle
        The vehicle being operated on.
    reservation : Reservation
        The reservation that grants access to the vehicle.
    tasks : list of VehicleTask[Vehicle]
        The tasks to execute sequentially.
    holder : User or None
        The user who will actively use the vehicle, or None for operator
        use.
    """

    __slots__ = ("_env", "_holder", "_reservation", "_sim", "_tasks", "_vehicle")

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: Vehicle,
        reservation: Reservation,
        tasks: list[VehicleTask[Vehicle]],
        holder: User | None = None,
    ) -> None:
        super().__init__(sim)
        self._env = sim.env
        self._sim = sim
        self._vehicle = vehicle
        self._reservation = reservation
        self._tasks = tasks
        self._holder = holder
        self.logger.debug(
            "Session initialized for vehicle %s with %s task(s), holder=%s",
            self._vehicle.uid,
            len(self._tasks),
            self._holder,
        )

    def execute(self) -> Generator[Event, None, None]:
        """Execute the session.

        Yields
        ------
        Event
            SimPy events during session execution.
        """
        try:
            # 1. Wait for vehicle availability (skip if already fulfilled)
            if not self._reservation.ready_event.triggered:
                self.logger.debug(
                    "Session waiting for reservation for vehicle %s, holder=%s.",
                    self._vehicle.uid,
                    self._holder,
                )
                try:
                    yield self._reservation.ready_event
                except ReservationCanceledError as err:
                    self.logger.debug(
                        "Session aborted before acquire_use for vehicle %s, holder=%s: %s",
                        self._vehicle.uid,
                        self._holder,
                        err,
                    )
                    raise

            # 2. Acquire exclusive use (auto-releases reservation)
            self._acquire_use()

            self.logger.debug(
                "Session started for vehicle %s with %s task(s), holder=%s",
                self._vehicle.uid,
                len(self._tasks),
                self._holder,
            )

            # 3. Calculate predicted energy and duration for entire session
            self._set_session_predictions()

            # 4. Execute tasks sequentially
            for task in self._tasks:
                yield from task.execute()
                if task.state is TaskState.ABORTED:
                    self.logger.debug("Session stopping early: task aborted.")
                    break

        finally:
            # 5. Always release vehicle use
            if (
                isinstance(self._vehicle, ReservableInterface)
                and self._vehicle.is_in_use
            ):
                self._vehicle.release_use()
                self.logger.debug(
                    "Session for vehicle %s ended, use released.", self._vehicle.uid
                )

    def _acquire_use(self) -> None:
        if isinstance(self._vehicle, ReservableInterface):
            self._vehicle.acquire_use(self._reservation, holder=self._holder)

    def _set_session_predictions(self) -> None:
        """Predict energy, duration, and destination for the entire session.

        A tasks predicted energy and duration can depend on the preceding tasks,
        so we iterate through all tasks sequentially.
        For the destination, we set it based on the last task that holds the attribute.
        """
        running_energy = self._vehicle.energy_system.current_energy_absolute
        total_duration = 0.0

        for task in self._tasks:
            energy_delta = task.get_predicted_energy_delta(running_energy)
            running_energy += energy_delta
            total_duration += task.get_predicted_duration(running_energy)

        self._vehicle.energy_system.predicted_energy = running_energy
        self._vehicle.estimated_completion_time = self._env.now + total_duration
        for task in reversed(self._tasks):
            if task.destination is not None:
                self._vehicle.destination = task.destination
                break

        total_energy_delta = (
            running_energy - self._vehicle.energy_system.current_energy_absolute
        )
        self.logger.debug(
            "Session predictions for vehicle %s: destination=%s, energy_delta=%.2f kWh, duration=%.1f min.",
            self._vehicle.uid,
            self._vehicle.destination,
            total_energy_delta,
            total_duration,
        )
