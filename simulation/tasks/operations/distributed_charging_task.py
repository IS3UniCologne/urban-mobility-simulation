"""VehicleTask for autonomous vehicle charging at a distributed charging station."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from simulation.helper.enums import PropulsionType
from simulation.tasks.base.vehicle_task import VehicleTask

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.infrastructure.charging_stations.charging_station import (
        ChargingStation,
    )
    from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

logger = logging.getLogger(__name__)


class DistributedChargingTask(VehicleTask["RideHailingVehicle"]):
    """Autonomous vehicle charging at distributed station with queue management.

    Lifecycle:

    1. Wait for timeslot (if applicable)
    2. Queue for charging plug
    3. Charge vehicle
    4. Unplug and return to service

    The task will abort if:
    - Missed timeslot (arrived too late)
    - Queue full (charging station at capacity)
    - Invalid charging duration (waited for slot but no time left to charge)

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : RideHailingVehicle
        The vehicle to charge.
    charging_duration : float
        Duration to charge the vehicle (in minutes).
    charging_station : ChargingStation
        The charging station to use.
    scheduled_time : float or None
        Scheduled timeslot start time (for virtual charging stations).
    arrived_at_charging_station : Event
        Event to signal arrival at charging station.
    started_charging : Event
        Event to signal charging start.
    """

    __slots__ = (
        "_arrived_at_charging_station",
        "_charging_duration",
        "_charging_station",
        "_estimated_completion_time",
        "_kWh_charged",
        "_scheduled_time",
        "_started_charging",
        "_waiting_time",
    )

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: RideHailingVehicle,
        charging_duration: float,
        charging_station: ChargingStation,
        scheduled_time: float | None,
        arrived_at_charging_station: Event,
        started_charging: Event,
    ) -> None:
        super().__init__(sim, vehicle)
        self._charging_duration = charging_duration
        self._charging_station = charging_station
        self._scheduled_time = scheduled_time
        self._arrived_at_charging_station = arrived_at_charging_station
        self._started_charging = started_charging
        self._waiting_time: float = 0.0
        self._kWh_charged: float = 0.0
        self._estimated_completion_time: float = 0.0

    @property
    def waiting_time(self) -> float:
        """Get the waiting time at the charging station."""
        return self._waiting_time

    @property
    def kWh_charged(self) -> float:
        """Get kWh charged."""
        return self._kWh_charged

    @property
    def estimated_completion_time(self) -> float:
        """Get the estimated completion time."""
        return self._estimated_completion_time

    def _run(self) -> Generator[Event, None, None]:
        vehicle = self._vehicle

        if vehicle.propulsion_type != PropulsionType.BATTERY_ELECTRIC:
            logger.error(
                "Vehicle %s has unsupported propulsion type %s for charging task.",
                vehicle.uid,
                vehicle.propulsion_type,
            )
            raise ValueError("Unsupported propulsion type for charging task.")

        vehicle.wait_for_charging()
        waiting_start = self._env.now

        timeslot_end = self._charging_station.timeslot_end(self._scheduled_time)
        if timeslot_end is not None:
            # wait for the reserved slot to begin
            assert self._scheduled_time is not None
            self._waiting_time = max(0.0, self._scheduled_time - self._env.now)
            if self._waiting_time > 0:
                logger.debug(
                    "Vehicle %s waits %s minutes for reserved slot.",
                    vehicle.uid,
                    self._waiting_time,
                )
                yield self._env.timeout(self._waiting_time)
            elif timeslot_end <= self._env.now:
                logger.warning(
                    "Vehicle %s arrived %s minutes at charging station after scheduled slot has ended. Cannot charge!",
                    vehicle.uid,
                    self._env.now - timeslot_end,
                )
                # Abort: missed timeslot
                # TODO: Decide whether arrival should be signaled before aborting to unblock capacity updates.
                vehicle.abort_charging_wait()
                self._abort()

        # sanity check if the physical capacity is not exhausted
        check_station_full = (
            len(self._charging_station.plugs.users)
            >= self._charging_station.plugs.capacity
        )

        if check_station_full and self._charging_station.queue_size <= len(
            self._charging_station.plugs.queue
        ):
            # charging station is at capacity and the queue is also full
            logger.info(
                "Vehicle %s arrived charging station, but the queue is full. Cannot charge!",
                vehicle.uid,
            )
            # Abort: queue full
            # TODO: Decide whether arrival should be signaled before aborting to unblock capacity updates.
            vehicle.abort_charging_wait()
            self._abort()

        with self._charging_station.plugs.request() as req:
            req.charging_duration = self._charging_duration  # type: ignore[attr-defined]
            req.estimated_completion_time = None  # type: ignore[attr-defined]
            yield req

            actual_duration = self._charging_duration
            if timeslot_end is not None:
                actual_duration = min(actual_duration, timeslot_end - self._env.now)

            if actual_duration <= 0:
                logger.info(
                    "Vehicle %s has a fishy charging time of %s minutes. Cannot charge!",
                    vehicle.uid,
                    actual_duration,
                )
                # Abort: invalid charging duration
                # TODO: Decide whether arrival should be signaled before aborting to unblock capacity updates.
                vehicle.abort_charging_wait()
                self._abort()

            actual_duration -= 1e-6 if actual_duration > 1e-6 else 0

            self._kWh_charged = actual_duration / 60 * self._charging_station.power
            self._estimated_completion_time = self._env.now + actual_duration
            req.charging_duration = actual_duration  # type: ignore[attr-defined]
            req.estimated_completion_time = self._estimated_completion_time  # type: ignore[attr-defined]

            # TODO: This is kind of late to signal arrival, we've already been waiting for the queue.
            self._arrived_at_charging_station.succeed()
            vehicle.plug_to_charging_station()
            self._env.process(self._charging_station.plug_in_notify())

            if timeslot_end is None:
                self._waiting_time = self._env.now - waiting_start

            self._started_charging.succeed(self._env.now)

            yield self._env.process(vehicle.charge(actual_duration, self._kWh_charged))

        vehicle.unplug_from_charging_station()
        self._env.process(self._charging_station.plug_out_notify())

    def get_predicted_energy_delta(self, current_energy: float | None = None) -> float:
        """Calculate predicted energy gain from charging.

        Relocation energy is predicted by the separate relocation task.

        Parameters
        ----------
        current_energy : float or None
            Running energy level from previous tasks. When None, uses
            vehicle's actual current energy.

        Returns
        -------
        float
            Energy delta in kWh (positive = energy gain).
        """
        vehicle = self._vehicle
        if current_energy is None:
            current_energy = vehicle.energy_system.current_energy_absolute

        charging_energy_gain = min(
            self._kWh_charged if self._kWh_charged > 0 else float("inf"),
            vehicle.energy_system.capacity - current_energy,
        )

        return charging_energy_gain

    def get_predicted_duration(self, current_energy: float | None = None) -> float:
        """Calculate predicted duration for charging.

        Relocation duration is predicted by the separate relocation task.

        Parameters
        ----------
        current_energy : float or None
            Running energy level from previous tasks. Unused; duration
            is pre-calculated for distributed charging.

        Returns
        -------
        float
            Predicted duration in minutes (charging only).
        """
        return self._charging_duration
