"""DTO for a ridehailing vehicle charging session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition

if TYPE_CHECKING:
    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.infrastructure.charging_stations.charging_station import (
        ChargingStation,
    )
    from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


@dataclass(slots=True)
class ChargingSession:
    """Data class representing a charging session."""

    destination: str
    start_time: float
    estimated_arrival_time: float
    scheduled_time: float | None
    charging_duration: float
    vehicle: RideHailingVehicle
    charging_station: ChargingStation
    arrived_at_charging_station: Event
    started_charging: Event

    finished: Event = None  # type: ignore[assignment]

    # Results
    waiting_time: float | None = None
    kWh_charged: float | None = None
    estimated_completion_time: float | None = None

    @classmethod
    def create(
        cls,
        sim: SimulationContext,
        vehicle: RideHailingVehicle,
        charging_station: ChargingStation,
        scheduled_time: float | None = None,
    ) -> ChargingSession:
        """Create a charging session.

        Parameters
        ----------
        sim : SimulationContext
            Simulation context.
        vehicle : RideHailingVehicle
            Vehicle to charge.
        charging_station : ChargingStation
            Target charging station.
        scheduled_time : float or None
            Reserved timeslot start time.

        Returns
        -------
        ChargingSession
        """
        destination = charging_station.location
        dest_position = GeodesicPosition(
            sim, *sim.geo_env.get_centroid(destination), destination
        )
        distance = vehicle.position << dest_position
        estimated_arrival_time = sim.env.now + distance / vehicle.velocity

        charging_duration = (
            (
                vehicle.energy_system.capacity
                - vehicle.energy_system.current_energy_absolute
                + vehicle.energy_system.calculate_energy_required(distance)
            )
            / charging_station.power
            * 60
        )
        timeslot_end = charging_station.timeslot_end(scheduled_time)
        if timeslot_end is not None and scheduled_time is not None:
            slot_window = max(0.0, timeslot_end - scheduled_time)
            charging_duration = min(charging_duration, slot_window)

        return cls(
            destination=destination,
            start_time=sim.env.now,
            estimated_arrival_time=estimated_arrival_time,
            scheduled_time=scheduled_time,
            charging_duration=charging_duration,
            vehicle=vehicle,
            charging_station=charging_station,
            arrived_at_charging_station=sim.env.event(),
            started_charging=sim.env.event(),
            finished=sim.env.event(),
        )
