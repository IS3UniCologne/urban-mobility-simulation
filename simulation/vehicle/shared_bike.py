from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedBike(SharedVehicle):
    # Shared Bike Counter
    shared_bike_id = 0

    __slots__ = (
        "_velocity",
        "_max_available_seats",
        "_max_state_of_charge",
        "_energy_consumption",
        "_price_per_min",
        "_shared_bike_id",
    )

    def __init__(
        self,
        env: Environment,
        position,
        velocity,
        max_available_seats=1,
        max_state_of_charge=0,
        price_per_min=0.08,
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
            velocity,
            max_available_seats,
            max_state_of_charge,
            0.0,
            price_per_min,
        )

        # Increment Shared Car ID
        self._shared_bike_id = SharedBike.shared_bike_id

        SharedBike.shared_bike_id += 1

    def _update_state_of_charge(self, distance):
        pass

    def has_enough_state_of_charge(self, distance):
        return True
