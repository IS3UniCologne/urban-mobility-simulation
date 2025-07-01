from simpy import Environment

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleMode
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class RideHailingAV(RideHailingVehicle):
    # Autonomous Ride Hailing Car Counter
    ride_hailing_av_id: int = 0
    vehicle_type: str = "ridehailing_AV"

    __slots__ = ("_emergency_soc_buffer_percent", "_price_per_min", "car_id")

    def __init__(  # noqa: ANN204
        self,
        env: Environment,
        fleet,  # noqa: ANN001
        position: GeodesicPosition,
        velocity: float,
        max_available_seats: int = 4,
        max_state_of_charge: float = 16.7,
        energy_consumption: float = 0.152,
        price_per_min: float = 0.26,
    ):
        """

        :param env:
        :param position:
        :param max_available_seats: 16.7 kWH as per Smart EQ specification 16.7
        (see e.g.g, https://www.smart.com/de/de/modelle/smart-eq-fortwo-coupe#technische-daten-smart-eq-fortwo-coupe)
        :param max_state_of_charge:
        :param energy_consumption: 15.2 kWh/100km as per Smart EQ specification
        :param velocity:
        """
        super(RideHailingAV, self).__init__(  # noqa: UP008
            env,
            fleet,
            position,
            velocity,
            VehicleMode.Car,
            max_available_seats,
            max_state_of_charge,
            energy_consumption,
            price_per_min,
            is_electric=True,
        )

        # Increment Shared Car ID
        self.car_id: int = RideHailingAV.ride_hailing_av_id
        self._price_per_min: float = price_per_min
        self._emergency_soc_buffer_percent: float = self._config.ride_hailing_vehicles[
            "AutonomousCar"
        ].EMERGENCY_SOC_BUFFER
        RideHailingAV.ride_hailing_av_id += 1
