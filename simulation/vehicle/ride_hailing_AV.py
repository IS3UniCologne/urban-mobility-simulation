from simpy import Environment

from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class RideHailingAV(RideHailingVehicle):
    # Autonomous Ride Hailing Car Counter
    ride_hailing_av_id = 0
    vehicle_type = "ridehailing_AV"

    __slots__ = ("car_id", "_price_per_min", "_emergency_soc_buffer_percent")

    def __init__(
        self,
        env: Environment,
        fleet,
        position,
        velocity,
        max_available_seats=4,
        max_state_of_charge=16.7,
        energy_consumption=0.152,
        price_per_min=0.26,
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
        super(RideHailingAV, self).__init__(
            env,
            fleet,
            position,
            velocity,
            max_available_seats,
            max_state_of_charge,
            energy_consumption,
            price_per_min,
            is_electric=True,
        )

        # Increment Shared Car ID
        self.car_id = RideHailingAV.ride_hailing_av_id
        self._price_per_min = price_per_min
        self._emergency_soc_buffer_percent = self._config.ride_hailing_vehicles[
            "AutonomousCar"
        ].EMERGENCY_SOC_BUFFER
        RideHailingAV.ride_hailing_av_id += 1
