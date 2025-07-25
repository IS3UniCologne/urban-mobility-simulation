from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.position import Position
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.operator.vehicle_fleet import VehicleFleet


class RideHailingAV(RideHailingVehicle):
    # Autonomous Ride Hailing Car Counter
    ride_hailing_av_id: int = 0
    vehicle_type: str = "ridehailing_AV"

    __slots__ = ("_emergency_soc_buffer_percent", "_price_per_min", "car_id")

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        position: Position,
        vehicle_config: VehicleConfig,
    ) -> None:
        """

        :param sim:
        :param position:
        :param max_available_seats: 16.7 kWH as per Smart EQ specification 16.7
        (see e.g.g, https://www.smart.com/de/de/modelle/smart-eq-fortwo-coupe#technische-daten-smart-eq-fortwo-coupe)
        :param max_state_of_charge:
        :param energy_consumption: 15.2 kWh/100km as per Smart EQ specification
        :param velocity:
        """
        super().__init__(
            sim=sim, fleet=fleet, position=position, vehicle_config=vehicle_config
        )

        # Increment Shared Car ID
        self.car_id: int = RideHailingAV.ride_hailing_av_id
        self._price_per_min: float = vehicle_config.PRICE_PER_MIN
        self._emergency_soc_buffer_percent: float = (
            self._sim.config.ride_hailing_vehicles["AutonomousCar"].EMERGENCY_SOC_BUFFER
        )
        RideHailingAV.ride_hailing_av_id += 1
