from simpy import Environment
import logging

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedBike(SharedVehicle):
    # Shared Kick Scooter Counter
    shared_bike_id = 0

    def __init__(
        self,
        env: Environment,
        position,
        max_available_seats=1,
        velocity=333.33,
        price_per_min=0.19,
    ):
        """

        :param env:
        :param position:
        :param max_available_seats:
        (see e.g, https://www.okai.co/products/es200) vendor of Tier (8aH, 36V => 288Wh)
        :param velocity:
        """
        super(SharedBike, self).__init__(
            env,
            position,
            max_available_seats,
            1,
            0.0,
            velocity,
            price_per_min
        )

        # Increment Shared Car ID
        self._shared_bike_id = SharedBike.shared_bike_id

        SharedBike.shared_bike_id += 1

    def _update_state_of_charge(self, distance):
        """
        Update state of charge of vehicles based on driven distance.
        SoC = SoC_old - EnergyConsumption (kWh/km) * km
        :param distance: Distance driven
        """

        logging.debug(
            f"Skip Charge updating of Bike"
        )