from simpy import Environment

from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class AutonomousCar(RideHailingVehicle):
    # Shared Care Counter
    ride_hailing_car_id = 0

    def __init__(
        self,
        env: Environment,
        position,
        max_available_seats=4,
        max_state_of_charge=16.7,
        energy_consumption=0.152,
        velocity=833.33,
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
        super(AutonomousCar, self).__init__(
            env,
            position,
            max_available_seats,
            max_state_of_charge,
            energy_consumption,
            velocity,
            price_per_min,
        )

        # Increment Shared Car ID
        self.car_id = AutonomousCar.ride_hailing_car_id
        self._price_per_minute = price_per_min
        self.electric_vehicle = True
        AutonomousCar.ride_hailing_car_id += 1
